from __future__ import annotations

from types import ModuleType
from typing import Callable
from typing import Generator
from typing import Dict
from typing import List
from typing import Set
from typing import Type
from typing import Tuple

import abc
import collections
import gettext
import importlib
import logging
import os


__all__ = [
    "noop",
    "PluginBase",
    "Core",
    "MINIMUM_CONFIG_PLUGINS",
    "RECOMMENDED_PLUGINS",
]


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
    'openpaperwork_core.crypto.certificates.selfsigned',
    'openpaperwork_core.crypto.certificates.store',
    'openpaperwork_core.external_apps.dbus',
    'openpaperwork_core.external_apps.windows',
    'openpaperwork_core.external_apps.xdg',
    'openpaperwork_core.flatpak',
    'openpaperwork_core.fs.memory',
    'openpaperwork_core.http.client',
    'openpaperwork_core.http.server',
    'openpaperwork_core.i18n.python',
    'openpaperwork_core.l10n.python',
    'openpaperwork_core.networking',
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
        'openpaperwork_core.networking.zeroconf',
    ]


def _(s):
    return gettext.dgettext('openpaperwork_core', s)


def _pretty_method_name(method):
    name = (
        method.name
        if hasattr(method, "name")
        else method.__qualname__
    )
    return f"{method.__module__}.{name}"


def noop(func):
    """Decorator to mark a method/callback as empty (for optimization)."""
    func._is_empty = True
    return func


class DependencyException(Exception):
    """
    Failed to satisfy dependencies.
    """
    pass


class PluginBase:
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

    def __init__(self, core: Core):
        """
        Called as soon as the module is loaded. Should be as minimal as
        possible. Most of the work should be done in `init()`.
        You *must* *not* rely on any dependencies here.
        """
        self.core: Core = core  # type: ignore

    @classmethod
    def get_interfaces(cls):
        """
        Indicates the list of interfaces implemented by this plugin.
        Interface names are arbitrarily defined. Methods provided by each
        interface are arbitrarily defined (and no checks are done).

        Returns a list of string.
        """
        return [
            c
            for c in cls.mro()
            if (
                (c is not abc.ABC)
                and (c is not cls)
                and issubclass(c, abc.ABC)
            )
        ]

    @classmethod
    def get_deps(cls):
        """
        Return the dependencies required by this plugin.

        Example:

        .. code-block:: python

          [
            {
              "interface": some_pure_abstract_class,  # required
              "defaults": ['plugin_a', 'plugin_b'],  # required
              "optional": False,  # optional
            },
          ]
        """
        return []


class _Module:
    def __init__(self, module: ModuleType, plugins_kwargs: Dict):
        self.module = module
        self.plugin_kwargs = plugins_kwargs

    def __eq__(self, o):
        return self.module == o.module

    def __hash__(self):
        return hash(self.module.__name__)

    def __str__(self):
        return self.module.__name__

    def __repr__(self):
        return str(self)


class _ModuleRepository:
    def __init__(self):
        self.modules: Dict[str, _Module] = {}
        self.interface_to_modules: Dict[Type[abc.ABC], List[_Module]] = (
            collections.defaultdict(list)
        )

    def add(self, module_name: str, module: ModuleType | None, plugin_kwargs):
        if module is None:
            LOGGER.info("Loading module '%s' ...", module_name)
            module = importlib.import_module(module_name)
        m = _Module(module, plugin_kwargs)
        self.modules[module_name] = m
        for interface in module.Plugin.get_interfaces():
            assert not isinstance(interface, str), \
                 f"Plugin '{module}' specify interface '{interface}' in" \
                 " old-style (str instead of abstract-class)"
            self.interface_to_modules[interface].append(m)
        return m

    def get_by_name(self, module_name: str) -> _Module:
        return self.modules[module_name]

    def get_by_interface(self, interface: Type[abc.ABC]) -> List[_Module]:
        return self.interface_to_modules[interface]

    def get_missing_dependencies(self):
        LOGGER.info("Looking for missing dependencies ...")
        modules = self.modules.values()
        for module in modules:
            for dep in module.module.Plugin.get_deps():
                if dep.get("optional", False):
                    continue
                interface = dep["interface"]
                if len(self.interface_to_modules[interface]) > 0:
                    continue
                yield (
                    module,
                    interface,
                    dep["defaults"],
                )


class _DependencyTreeNode:
    def __init__(self, module: _Module):
        self.module = module
        self.depends_on = set()
        self.required_by = set()

    def __hash__(self):
        return hash(str(self.module))

    def __eq__(self, o):
        return self.module == o.module

    def __str__(self):
        return str(self.module)

    def __repr__(self):
        return str(self.module)

    def load_deps(self, dep_tree: _DependencyTree):
        for dep in self.module.module.Plugin.get_deps():
            if dep.get("optional", False):
                continue
            interface = dep["interface"]
            nodes = dep_tree.get_nodes_by_interface(interface)
            for node in nodes:
                self.depends_on.add(node)
                node.required_by.add(self)

    def log(self, depth):
        if depth > 10:
            return
        LOGGER.info(("|   " * depth) + f"|-- {self.module}")
        for node in self.depends_on:
            node.log(depth + 1)

    def find_dependency_loop(self, stack: List[_DependencyTreeNode]):
        if self in stack:
            LOGGER.critical(f"Dependency loop: {stack}")
            return True
        stack.append(self)
        has_loop = False
        for dep in self.depends_on:
            has_loop = dep.find_dependency_loop(stack) or has_loop
        stack.pop(-1)
        return has_loop

    def get_init_order(
            self, already_yielded: Set[_Module]
    ) -> Generator[_Module, None, None]:
        for dep in self.depends_on:
            for module in dep.get_init_order(already_yielded):
                if module in already_yielded:
                    continue
                yield module
        yield self.module


class _DependencyTree:
    def __init__(self, module_repository: _ModuleRepository):
        self.module_repository = module_repository
        self._interface_to_nodes: Dict[Type[abc.ABC], List[_DependencyTreeNode]] = (
            collections.defaultdict(list)
        )
        self.nodes = [_DependencyTreeNode(module) for module in module_repository.modules.values()]
        for node in self.nodes:
            for interface in node.module.module.Plugin.get_interfaces():
                self._interface_to_nodes[interface].append(node)
        for node in self.nodes:
            node.load_deps(self)
        self.roots = [
            node
            for node in self.nodes
            if len(node.required_by) <= 0
        ]

    def get_nodes_by_interface(self, interface: Type[abc.ABC]) -> List[_DependencyTreeNode]:
        return self._interface_to_nodes[interface]

    def log(self):
        LOGGER.info("Plugin dependency tree (%d nodes)", len(self.nodes))
        for root in self.roots:
            root.log(depth=0)

    def find_dependency_loop(self):
        LOGGER.info("Looking for dependency loops")
        has_loop = False
        for root in self.nodes:
            stack = []
            has_loop = root.find_dependency_loop(stack) or has_loop
        if has_loop:
            raise DependencyException("Dependency loop detected")

    def get_init_order(self) -> Generator[_Module, None, None]:
        already_yielded = set()
        for root in self.roots:
            for module in root.get_init_order(already_yielded):
                if module in already_yielded:
                    continue
                already_yielded.add(module)
                yield module


class _Stub:
    def __init__(self, name):
        self.name = name

    @property
    def __self__(self):
        return self

    @property
    def __name__(self):
        return self.name

    def __call__(self, *args, **kwargs):
        LOGGER.debug("%s() called, but no one is listening", self.name)


class _CoreProxy:
    """
    Allow a plugin to call methods only from the dependencies it has declared.
    Plugins must not and cannot call methods of undeclared dependencies.
    """
    def __init__(self, core: Core, module: _Module):
        self._core = core
        self._module = module
        self._callbacks: Dict[Callable, List[Callable]] = {}
        self._reload(init=True)

    def __str__(self) -> str:
        return f"_CoreProxy('{self._module}')"

    def __repr__(self) -> str:
        return str(self)

    def call_all(self, abstract_callback: Callable, *args, **kwargs):
        """
        See documentation of `Core.call_all()`
        """
        assert not isinstance(abstract_callback, str)  # old style calling
        self._check_callback_available(abstract_callback)
        callbacks = self._callbacks[abstract_callback]
        for callable in callbacks:
            callable(*args, **kwargs)
        return len(callbacks)

    def call_one(self, abstract_callback: Callable, *args, **kwargs):
        """
        See documentation of `Core.call_one()`
        """
        assert not isinstance(abstract_callback, str)  # old style calling
        self._check_callback_available(abstract_callback)
        return self._callbacks[abstract_callback][0](*args, **kwargs)

    def call_success(self, abstract_callback: Callable, *args, **kwargs):
        """
        See documentation of `Core.call_success()`
        """
        assert not isinstance(abstract_callback, str)  # old style calling
        self._check_callback_available(abstract_callback)
        for callable in self._callbacks[abstract_callback]:
            r = callable(*args, **kwargs)
            if r is not None:
                return r
        return None

    def load(self, *args, **kwargs):
        """
        See documentation of `Core.load()`
        """
        self._core.load(*args, **kwargs)

    def init(self, *args, **kwargs):
        """
        See documentation of `Core.init()`
        """
        self._core.init(*args, **kwargs)

    def get_by_name(self, module_name: str) -> PluginBase:
        return self._core.get_by_name(module_name)

    def get_by_interface(self, interface: Type[abc.ABC]) -> List[PluginBase]:
        return self._core.get_by_interface(interface)

    def __add_interface_callbacks(self, interface: Type[abc.ABC], optional=False):
        for abstract_method_name in dir(interface):
            if abstract_method_name.startswith("_"):
                continue
            if abstract_method_name in dir(PluginBase):
                continue
            abstract_method = getattr(interface, abstract_method_name)
            if not hasattr(abstract_method, "__call__"):
                continue
            concrete_methods = self._core._plugin_repository.abstract_method_to_concrete.get(
                abstract_method, []
            )
            if len(concrete_methods) > 0:
                concrete_methods = [c[2] for c in concrete_methods]
            else:
                concrete_methods = [_Stub(f"{interface}.{abstract_method_name}")]
            for concrete in concrete_methods:
                LOGGER.debug(
                    "%s -> %s.%s() -> %s",
                    self._module,
                    interface.__name__, abstract_method_name,
                    _pretty_method_name(concrete),
                )
            self._callbacks[abstract_method] = concrete_methods

    def _reload(self, init=False):
        self._callbacks = {}
        for dep in self._module.module.Plugin.get_deps():
            self.__add_interface_callbacks(dep["interface"], optional=dep.get("optional", False))
        if not init:  # the plugin has been initialized and can therefore self-reference
            for interface in self._module.module.Plugin.get_interfaces():
                self.__add_interface_callbacks(interface)

    def _check_callback_available(self, abstract_callback: Callable):
        if abstract_callback in self._callbacks:
            return
        LOGGER.error("-----")
        LOGGER.error("Callback '%s' cannot be called from %s", abstract_callback, self._module)
        LOGGER.error("%s has only declared dependencies for the following callbacks:", self._module)
        for abstract_callback in self._callbacks.keys():
            LOGGER.error("- %s", _pretty_method_name(abstract_callback))
        LOGGER.error("-----")


class _PluginRepository:
    def __init__(self, core: Core):
        self.core = core
        self.module_to_plugin: Dict[_Module, PluginBase] = {}
        self.interface_to_plugins: Dict[Type[abc.ABC], List[PluginBase]] = (
            collections.defaultdict(list)
        )
        self.abstract_method_to_concrete: Dict[Callable, List[Tuple[int, str, Callable]]] = (
            collections.defaultdict(list)
        )
        self.core_proxies = []

    def add(self, module: _Module) -> PluginBase:
        plugin = self.module_to_plugin.get(module, None)
        if plugin is not None:
            return plugin

        LOGGER.info("Initializing '%s' ...", module)

        core_proxy = _CoreProxy(self.core, module)
        self.core_proxies.append(core_proxy)

        plugin = module.module.Plugin(core_proxy, **module.plugin_kwargs)
        self.module_to_plugin[module] = plugin
        for interface in plugin.get_interfaces():
            self.interface_to_plugins[interface].append(plugin)

        methods_to_register = dir(plugin)
        methods_to_register = {
            m
            for m in methods_to_register
            if not m.startswith("_") and m not in dir(PluginBase)
        }
        methods_to_register = {
            m
            for m in methods_to_register
            if hasattr(getattr(plugin, m), "__call__")
        }
        has_abstract_parent = False
        abstract_classes = plugin.get_interfaces()
        callback_defined = set()
        for abstract_cls in abstract_classes:
            has_abstract_parent = True
            for func_name in dir(abstract_cls):
                if func_name.startswith("_"):
                    continue
                if func_name in dir(PluginBase):
                    continue
                abstract_callback = getattr(abstract_cls, func_name)
                if not hasattr(abstract_callback, "__call__"):
                    continue
                if abstract_callback in callback_defined:
                    continue
                LOGGER.debug(
                    "%s.%s() <- %s.%s()",
                    plugin.__module__, func_name, abstract_cls.__name__, func_name
                )
                callback_defined.add(abstract_callback)
                plugin_callback = getattr(plugin, func_name)
                if getattr(plugin_callback, '_is_empty', False):
                    LOGGER.debug("Method '%s' is empty and has been ignored", plugin_callback)
                else:
                    self.abstract_method_to_concrete[abstract_callback].append((
                        plugin.PRIORITY, str(type(plugin)), plugin_callback
                    ))
                try:
                    methods_to_register.remove(func_name)
                except KeyError:
                    pass

        for concretes in self.abstract_method_to_concrete.values():
            concretes.sort(reverse=True)

        assert \
            has_abstract_parent, \
            f"Plugin {plugin} doesn't implement any abstract class"
        assert \
            len(methods_to_register) <= 0, \
            f"Plugin {plugin} provides method(s) {methods_to_register}, but" \
            " no interface defines them"

        return plugin

    def get_by_module(self, module: _Module) -> PluginBase:
        return self.module_to_plugin[module]

    def get_by_interface(self, interface: Type[abc.ABC]) -> List[PluginBase]:
        return self.interface_to_plugins[interface]

    def reload_all_core_proxies(self):
        for core_proxy in self.core_proxies:
            core_proxy._reload(init=False)

    def call_all(self, abstract_callback: Callable, *args, **kwargs):
        assert not isinstance(abstract_callback, str)  # old style calling
        callbacks = self.abstract_method_to_concrete[abstract_callback]
        for (_, _, callable) in callbacks:
            callable(*args, **kwargs)
        return len(callbacks)

    def call_one(self, abstract_callback: Callable, *args, **kwargs):
        assert not isinstance(abstract_callback, str)  # old style calling
        return self.abstract_method_to_concrete[abstract_callback][0][-1](*args, **kwargs)

    def call_success(self, abstract_callback: Callable, *args, **kwargs):
        assert not isinstance(abstract_callback, str)  # old style calling
        for (_, _, callable) in self.abstract_method_to_concrete[abstract_callback]:
            r = callable(*args, **kwargs)
            if r is not None:
                return r
        return None


class Core:
    """
    Manage plugins and their callbacks.
    """
    def __init__(self, auto_load_dependencies=False):
        """
        `auto_load_dependencies=True` means that missing dependencies will be
        loaded automatically based on the default plugin list provided by
        plugins. This should be only used for testing.
        """
        self._auto_load_dependencies = auto_load_dependencies
        self._module_repository = _ModuleRepository()
        self._plugin_repository = _PluginRepository(self)

    def load(self, module_name: str, module: ModuleType | None = None, **kwargs):
        """
        - Load the specified module

        BEWARE of dependency loops !

        Arguments:
            - module_name: name of the Python module to load
        """
        self._module_repository.add(module_name, module, kwargs)

    def init(self):
        """
        - Instantiate all the Plugin
        - Make sure all the dependencies of all the plugins are satisfied.
        - Call the method init() of each plugin following the dependency
          order (those without dependencies are called first).

        BEWARE of dependency loops !
        """
        has_missing_dependencies = True
        while has_missing_dependencies:
            has_missing_dependencies = False
            missing_dependencies = list(self._module_repository.get_missing_dependencies())
            for (module, interface, defaults) in missing_dependencies:
                has_missing_dependencies = True
                if not self._auto_load_dependencies:
                    raise DependencyException(
                        f"{module} requires interfaces {str(interface)},"
                        f" but no loaded plugin implement it. Suggested: {defaults}"
                    )
                if len(defaults) <= 0:
                    raise DependencyException(
                        f"{module} requires interfaces {str(interface)},"
                        " but no default provided"
                    )
                for default in defaults:
                    LOGGER.info(
                        "Auto-loading '%s' because of '%s' requiring '%s'",
                        default, module, interface
                    )
                    m = self._module_repository.add(default, None, {})
                    if interface not in m.module.Plugin.get_interfaces():
                        raise DependencyException(
                            f"{default} was loaded to satisfy {module}"
                            f" dependency on {str(interface)},"
                            f" but {default} doesn't implement {str(interface)}"
                        )

        dep_tree = _DependencyTree(self._module_repository)
        dep_tree.find_dependency_loop()
        # dep_tree.log()

        for module in dep_tree.get_init_order():
            self._plugin_repository.add(module)

        # reload core proxies that were already existing before this init()
        self._plugin_repository.reload_all_core_proxies()

    def get_by_name(self, module_name: str) -> PluginBase:
        """
        Returns a Plugin instance based on the corresponding module name
        (assuming it has been loaded).

        You shouldn't use this function, except for:
        - unit tests
        - configuration (see cmd.plugins)
        """
        module = self._module_repository.get_by_name(module_name)
        plugin = self._plugin_repository.get_by_module(module)
        return plugin

    def get_by_interface(self, interface: Type[abc.ABC]) -> List[PluginBase]:
        return self._plugin_repository.get_by_interface(interface)

    def call_all(self, abstract_callback: Callable, *args, **kwargs):
        """
        Call all the methods of all the plugins that have implemented `abstract_callback`.
        Arguments are passed as is. Returned values are dropped
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
        return self._plugin_repository.call_all(abstract_callback, *args, **kwargs)

    def call_one(self, abstract_callback, *args, **kwargs):
        """
        Look for a plugin method implementing `abstract_callback` and calls it.
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
        return self._plugin_repository.call_one(abstract_callback, *args, **kwargs)

    def call_success(self, abstract_callback, *args, **kwargs):
        """
        Call methods of all the plugins that have implemented `abstract_callback`
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
        return self._plugin_repository.call_success(abstract_callback, *args, **kwargs)

    def get_active_plugins(self) -> List[str]:
        return sorted(self._module_repository.modules.keys())
