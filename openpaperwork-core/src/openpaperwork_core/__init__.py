import collections
import gettext
import importlib
import itertools
import logging
import os
import time


LOGGER = logging.getLogger(__name__)

MINIMUM_CONFIG_PLUGINS = [
    # You also have to provide a plugin providing the interface 'app'
    'openpaperwork_core.archives',
    'openpaperwork_core.cmd.config',
    'openpaperwork_core.cmd.ping',
    'openpaperwork_core.cmd.plugins',
    'openpaperwork_core.config',
    'openpaperwork_core.config.automatic_plugin_reset',
    'openpaperwork_core.config.backend.configparser',
    'openpaperwork_core.data_versioning',
    'openpaperwork_core.frozen',
    'openpaperwork_core.fs.python',
    'openpaperwork_core.logs.archives',
    'openpaperwork_core.mainloop.asyncio',
    'openpaperwork_core.paths.xdg',
    'openpaperwork_core.uncaught_exception',
]


RECOMMENDED_PLUGINS = [
    'openpaperwork_core.external_apps.dbus',
    'openpaperwork_core.external_apps.windows',
    'openpaperwork_core.external_apps.xdg',
    'openpaperwork_core.flatpak',
    'openpaperwork_core.fs.memory',
    'openpaperwork_core.http',
    'openpaperwork_core.i18n.python',
    'openpaperwork_core.l10n.python',
    'openpaperwork_core.perfcheck.log',
    'openpaperwork_core.resources.frozen',
    'openpaperwork_core.resources.setuptools',
    'openpaperwork_core.sqlite',
    'openpaperwork_core.thread.pool',
    'openpaperwork_core.urls',
    'openpaperwork_core.work_queue.default',
]

if os.name != 'nt':
    RECOMMENDED_PLUGINS += [
        'openpaperwork_core.cmd.chkdeps',
    ]


def _(s):
    return gettext.dgettext('openpaperwork_core', s)


class DependencyException(Exception):
    """
    Failed to satisfy dependencies.
    """
    pass


class PluginBase(object):
    """
    Indicates all the methods that must be implemented by any plugin
    managed by OpenPaperwork core. Also provides default implementations
    for each method.
    """

    # Priority defines in which order callbacks will be called.
    # Plugins with higher priorities will have their callbacks called first.
    PRIORITY = 0

    # Convenience for the applications: Indicates if users should be able
    # to enable/disable this plugin in the UI.
    USER_VISIBLE = False

    def __init__(self):
        """
        Called as soon as the module is loaded. Should be as minimal as
        possible. Most of the work should be done in `init()`.
        You *must* *not* rely on any dependencies here.
        """
        self.core = None

    def get_interfaces(self):
        """
        Indicates the list of interfaces implemented by this plugin.
        Interface names are arbitrarily defined. Methods provided by each
        interface are arbitrarily defined (and no checks are done).

        Returns a list of string.
        """
        return []

    def get_deps(self):
        """
        Return the dependencies required by this plugin.

        Example:

        .. code-block:: python

          [
            {
              "interface": "some_interface_name",  # required
              "defaults": ['plugin_a', 'plugin_b'],  # required
              "expected_already_satisfied": False,  # optional, default: True
            },
          ]
        """
        return []

    def init(self, core):
        """
        Plugins can initialize whatever they want here. When called, all
        dependencies have been loaded and initialized, so using them is safe.
        Does nothing by default.
        """
        self.core = core


class Core(object):
    """
    Manage plugins and their callbacks.
    """
    def __init__(self, auto_load_dependencies=False):
        """
        `auto_load_dependencies=True` means that missing dependencies will be
        loaded automatically based on the default plugin list provided by
        plugins. This should be only used for testing.
        """
        self.plugins = {}
        self.initialized = False
        self._to_initialize = set()
        self._initialized = set()  # avoid double-init
        self.interfaces = collections.defaultdict(list)
        self.callbacks = collections.defaultdict(list)
        self.auto_load_dependencies = auto_load_dependencies

        self.log_all = bool(os.getenv("CORE_LOG_ALL", 0))
        self.count_limit_per_second = int(os.getenv("CORE_CALL_LIMIT", 0))
        self.counters_last_reset = 0
        self.counters = collections.defaultdict(lambda: 0)

    def load(self, module_name):
        """
        - Load the specified module
        - Instantiate the class 'Plugin()' of this module
        - Register all the methods of this plugin object (except those starting
          by '_' and those from the class PluginBase) as callbacks

        BEWARE of dependency loops !

        Arguments:
            - module_name: name of the Python module to load
        """
        if module_name in self.plugins:
            return self.plugins[module_name]

        LOGGER.info("Loading plugin '%s' ...", module_name)
        module = importlib.import_module(module_name)
        return self._load_module(module_name, module)

    def _load_module(self, module_name, module):
        """
        should be called from outside for testing only
        """
        if module_name in self.plugins:
            LOGGER.debug("Module %s already loaded", module_name)
            return self.plugins[module_name]

        self.initialized = False

        plugin = module.Plugin()
        self.plugins[module_name] = plugin

        for interface in plugin.get_interfaces():
            LOGGER.debug("- '%s' provides '%s'", str(type(plugin)), interface)
            self.interfaces[interface].append(plugin)

        self._to_initialize.add(plugin)

        LOGGER.info("Plugin '%s' loaded", module_name)
        return plugin

    def _check_deps(self):
        to_examine = [
            (plugin_name, plugin)
            for (plugin_name, plugin) in self.plugins.items()
        ]

        while len(to_examine) > 0:
            (plugin_name, plugin) = to_examine[0]
            to_examine = to_examine[1:]

            LOGGER.info("Examining dependencies of '%s' ...", plugin_name)

            deps = plugin.get_deps()
            for dep in deps:
                interface = dep['interface']
                if len(self.interfaces[interface]) > 0:
                    LOGGER.debug(
                        "- Interface '%s' already provided by %d plugins",
                        interface, len(self.interfaces[interface])
                    )
                    continue

                defaults = dep['defaults']
                if len(defaults) <= 0:
                    continue

                if (not self.auto_load_dependencies
                        and (
                            'expected_already_satisfied' not in dep
                            or dep['expected_already_satisfied']
                        )):
                    LOGGER.warning(
                        "Plugin '{}' requires interface '{}' but no plugins"
                        " provide this interface (suggested: {}). Plugin '{}'"
                        " will not be initialized.".format(
                            plugin_name, interface, defaults, plugin_name
                        )
                    )
                    plugin = self.plugins.pop(plugin_name)
                    self._to_initialize.remove(plugin)
                    # return False to indicate we actually dropped a plugin
                    # and need to reevaluate all the dependencies again.
                    return False
                else:
                    LOGGER.info(
                        "Loading plugins %s to satisfy dependency."
                        " Required by '%s' for interface '%s'",
                        defaults, type(plugin), interface
                    )
                    for default in defaults:
                        to_examine.append((default, self.load(default)))

        return True

    def _register_plugin(self, plugin):
        for attr_name in dir(plugin):
            if attr_name[0] == "_":
                continue
            if attr_name in dir(PluginBase):  # ignore base methods of plugins
                continue
            callback = getattr(plugin, attr_name)
            if not hasattr(callback, '__call__'):
                continue
            LOGGER.debug("- %s.%s()", str(type(plugin)), attr_name)
            self.callbacks[attr_name].append((
                plugin.PRIORITY, str(type(plugin)), callback
            ))
            self.callbacks[attr_name].sort(reverse=True)

    def _init(self, plugin, stack=list()):
        nb = 0
        if plugin in self._initialized:
            return nb

        if plugin in stack:
            LOGGER.error("Dependency loop:")
            for p in itertools.chain(stack, [plugin]):
                LOGGER.error(
                    "- %s %s depends on %s",
                    p, p.get_interfaces(),
                    [d['interface'] for d in p.get_deps()]
                )
            raise DependencyException("Dependency loop: %s" % str(stack))

        stack.append(plugin)

        self.initialized = True

        deps = plugin.get_deps()
        for dep in deps:
            dep_plugins = self.interfaces[dep['interface']]
            for dep_plugin in dep_plugins:
                nb += self._init(dep_plugin, stack)

        LOGGER.info("Initializing plugin '%s' ...", type(plugin))
        stack.remove(plugin)
        plugin.init(self)

        self._register_plugin(plugin)
        nb += 1

        self._initialized.add(plugin)
        return nb

    def init(self):
        """
        - Make sure all the dependencies of all the plugins are satisfied.
        - Call the method init() of each plugin following the dependency
          order (those without dependencies are called first).

        BEWARE of dependency loops !
        """
        LOGGER.info("Initializing all plugins")
        while not self._check_deps():
            pass
        nb = 0
        for plugin in self._to_initialize:
            nb += self._init(plugin)
        self._to_initialize = set()
        LOGGER.info("%d plugins initialized", nb)

    def get_by_name(self, module_name):
        """
        Returns a Plugin instance based on the corresponding module name
        (assuming it has been loaded).

        You shouldn't use this function, except for:
        - unit tests
        - configuration (see cmd.plugins)
        """
        return self.plugins[module_name]

    def get_by_interface(self, interface_name):
        return self.interfaces[interface_name]

    def get_plugins(self):
        """
        You shouldn't use this function, except for:
        - unit tests
        - configuration (see cmd.plugins)
        """
        return dict(self.plugins)

    def _check_call_limit(self, callback_name):
        if self.count_limit_per_second <= 0:
            return
        now = time.time()
        if now - self.counters_last_reset >= 1.0:
            self.counters = collections.defaultdict(lambda: 0)
            self.counters_last_reset = now
        self.counters[callback_name] += 1
        if self.counters[callback_name] >= self.count_limit_per_second:
            raise Exception(
                "Too many calls to '{}' (>= {}) in one second".format(
                    callback_name, self.count_limit_per_second
                )
            )

    def call_all(self, callback_name, *args, **kwargs):
        """
        Call all the methods of all the plugins that have `callback_name`
        as name. Arguments are passed as is. Returned values are dropped
        (use callbacks for return values if required)

        Method call order is defined by the plugin priorities: Plugins with
        a higher priority get their methods called first.

        When we need a return value from callbacks called with `call_all()`,
        we need a way to get the results from all of them. The usual way to do
        that is to instantiate an empty `list` or `set`, and pass it as first
        argument of the callbacks (argument `out`). Callbacks can then
        complete this list or set using `list.append()` or `set.add()`.

        .. uml::

           Caller -> Core: call "func"
           Core -> "Plugin A": plugin.func()
           Core <- "Plugin A": returns "something_a"
           Core -> "Plugin B": plugin.func()
           Core <- "Plugin B": returns "something_b"
           Core -> "Plugin C": plugin.func()
           Core <- "Plugin C": returns "something_c"
           Caller <- Core: returns 3
        """
        if self.log_all:
            print(
                "[{}] call_all({}, args={}, kwargs={})".format(
                    time.time(), callback_name, args, kwargs
                )
            )

        assert \
            self.initialized, \
            "A plugin has been loaded without being initialized." \
            " Call core.init() first"

        self._check_call_limit(callback_name)

        callbacks = self.callbacks[callback_name]
        if len(callbacks) <= 0:
            if callback_name.startswith("on_"):
                # those are 'observer' callback. If nobody is observing,
                # it's usually fine.
                log_method = LOGGER.debug
            else:
                log_method = LOGGER.warning
            log_method("No method '%s' found", callback_name)
            return 0
        for (priority, plugin, callback) in callbacks:
            if self.log_all:
                print(
                    "[{}] call_all({}, args={}, kwargs={}) -> {}:{}".format(
                        time.time(), callback_name, args, kwargs,
                        priority, callback
                    )
                )
            callback(*args, **kwargs)
        return len(callbacks)

    def call_one(self, callback_name, *args, **kwargs):
        """
        Look for a plugin method called `callback_name` and calls it.
        Raises an error if no such method exists. If many exists,
        call one at random. Returns the value return by the callback.

        Method call order is defined by the plugin priorities: Plugins with
        a higher priority get their methods called first.

        .. uml::

           Caller -> Core: call "func"
           Core -> "Plugin A": plugin.func()
           Core <- "Plugin A": returns X
           Caller <- Core: returns X

        You're advised to use `call_all()` or `call_success()` instead
        whenever possible. This method is only provided as convenience for
        when you're fairly sure there should be only one plugin with such
        callback (example: mainloop plugins).
        """
        assert \
            self.initialized, \
            "A plugin has been loaded without being initialized." \
            " Call core.init() first"

        self._check_call_limit(callback_name)
        if self.log_all:
            print(
                "[{}] call_one({}, args={}, kwargs={})".format(
                    time.time(), callback_name, args, kwargs
                )
            )
        callbacks = self.callbacks[callback_name]
        if len(callbacks) <= 0:
            raise IndexError(
                "No method '{}' found !".format(callback_name)
            )
        if self.log_all:
            print(
                "[{}] call_one({}, args={}, kwargs={}) -> {}:{}".format(
                    time.time(), callback_name, args, kwargs,
                    callbacks[0][0], callbacks[0][2]
                )
            )
        return callbacks[0][2](*args, **kwargs)

    def call_success(self, callback_name, *args, **kwargs):
        """
        Call methods of all the plugins that have `callback_name`
        as name until one of them return a value that is not None.
        Arguments are passed as is. First value to be different
        from None is returned. If none of the callbacks returned
        a value different from None or if no callback has the
        specified name, this method will return None.

        Method call order is defined by the plugin priorities: Plugins with
        a higher priority get their methods called first.

        Callbacks should never raise any exception.

        .. uml::

           Caller -> Core: call "func"
           Core -> "Plugin A": plugin.func()
           Core <- "Plugin A": returns None
           Core -> "Plugin B": plugin.func()
           Core <- "Plugin B": returns None
           Core -> "Plugin C": plugin.func()
           Core <- "Plugin C": returns "something"
           Caller <- Core: returns "something"
        """
        assert \
            self.initialized, \
            "A plugin has been loaded without being initialized." \
            " Call core.init() first"

        self._check_call_limit(callback_name)
        if self.log_all:
            print(
                "[{}] call_one({}, args={}, kwargs={})".format(
                    time.time(), callback_name, args, kwargs
                )
            )
        callbacks = self.callbacks[callback_name]
        if len(callbacks) <= 0:
            LOGGER.warning("No method '%s' found", callback_name)
        for (priority, plugin, callback) in callbacks:
            if self.log_all:
                msg = "[{}] call_success({}, args={}, kwargs={}) -> {}:{}"
                print(msg.format(
                    time.time(), callback_name, args, kwargs, priority,
                    callback
                ))
            r = callback(*args, **kwargs)
            if r is not None:
                return r
        return None

    def get_deps(self, plugin_name):
        plugin = self.plugins[plugin_name]
        for dep in plugin.get_deps():
            if 'interface' not in dep:
                raise KeyError(
                    "Missing interface in dependency list of plugin"
                    " '{}'".format(plugin_name)
                )
            if 'defaults' not in dep:
                raise KeyError(
                    "Missing default plugins in dependency list of plugin"
                    " '{}' (interface={})".format(
                        plugin_name, dep['interface']
                    )
                )

            yield {
                'interface': dep['interface'],
                'actives': {
                    x.__module__
                    for x in self.get_by_interface(dep['interface'])
                },
                'defaults': set(dep['defaults']),
            }

    def get_active_plugins(self):
        return self.plugins.keys()
