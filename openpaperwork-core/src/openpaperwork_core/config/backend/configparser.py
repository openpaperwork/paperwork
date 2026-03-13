"""
Manages a configuration file using configparser.
"""

import collections
import configparser
import datetime
import logging

from openpaperwork_core import _
from openpaperwork_core.interfaces.bug_report_attachment import (
    BugReportAttachment
)
from openpaperwork_core.interfaces.config_backend import ConfigBackend
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.paths import Paths
import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class ConfigBool:
    def __init__(self, value=False):
        if isinstance(value, str):
            self.value = (value.lower() == 'true')
        else:
            self.value = value

    def __eq__(self, o):
        return (self.value == o)

    def __bool__(self):
        return self.value

    def __str__(self):
        return str(self.value)

    def get_value(self):
        return self.value


class ConfigDate:
    DATE_FORMAT = "%Y-%m-%d"

    def __init__(self, value=datetime.datetime(year=1971, month=1, day=1)):
        if isinstance(value, str):
            self.value = (
                datetime.datetime
                .strptime(value, self.DATE_FORMAT)
                .date()
            )
        else:
            self.value = value

    def __eq__(self, o):
        return (self.value == o)

    def __str__(self):
        return self.value.strftime(self.DATE_FORMAT)

    def get_value(self):
        return self.value


class ConfigList:
    SEPARATOR = ";"

    def __init__(self, value=None, elements=None):
        if elements is None:
            elements = []
        self.elements = elements

        if value is not None:
            if isinstance(value, str):
                if value != '':
                    elements = value.split(self.SEPARATOR)
                    for i in elements:
                        (t, v) = i.split(_TYPE_SEPARATOR, 1)
                        self.elements.append(_STR_TO_TYPE[t](v))
            elif hasattr(value, 'elements'):
                self.elements = value.elements[:]
            else:
                self.elements = list(value)

    def __iter__(self):
        return iter(self.elements)

    def __contains__(self, o):
        return o in self.elements

    def __getitem__(self, *args, **kwargs):
        return self.elements.__getitem__(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        return self.elements.__setitem__(*args, **kwargs)

    def __len__(self):
        return len(self.elements)

    def append(self, value):
        self.elements.append(value)

    def remove(self, value):
        self.elements.remove(value)

    def __str__(self):
        out = []
        for e in self.elements:
            out.append("{}{}{}".format(
                _TYPE_TO_STR[type(e)], _TYPE_SEPARATOR, str(e)
            ))
        return self.SEPARATOR.join(out)

    def get_value(self):
        return [
            e.get_value()
            if hasattr(e, 'get_value')
            else e
            for e in self.elements
        ]


class ConfigDict:
    SEPARATOR_ITEMS = ";"
    SEPARATOR_KEYVALS = "="

    def __init__(self, value=None, elements={}):
        self.elements = elements

        if value is not None:
            if isinstance(value, str):
                elements = value.split(self.SEPARATOR_ITEMS)
                for i in elements:
                    (k, v) = i.split(self.SEPARATOR_KEYVALS, 1)
                    (t, v) = v.split(_TYPE_SEPARATOR, 1)
                    self.elements[k] = _STR_TO_TYPE[t](v)
            elif hasattr(value, 'elements'):
                self.elements = value.elements[:]
            else:
                self.elements = dict(value)

    def __iter__(self):
        return iter(self.elements)

    def __contains__(self, o):
        return o in self.elements

    def __getitem__(self, *args, **kwargs):
        return self.elements.__getitem__(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        return self.elements.__setitem__(*args, **kwargs)

    def __len__(self):
        return len(self.elements)

    def __str__(self):
        out = []
        for (k, v) in self.elements.items():
            out.append("{}{}{}{}{}".format(
                k, self.SEPARATOR_KEYVALS,
                _TYPE_TO_STR[type(v)], _TYPE_SEPARATOR, str(v)
            ))
        return self.SEPARATOR_ITEMS.join(out)

    def get_value(self):
        return {
            k: v.get_value()
            if hasattr(v, 'get_value')
            else v
            for (k, v) in self.elements.items()
        }


_TYPE_TO_STR = {
    bool: "bool",
    ConfigBool: "bool",
    ConfigDate: "date",
    ConfigDict: "dict",
    ConfigList: "list",
    datetime.date: "date",
    dict: "dict",
    float: "float",
    int: "int",
    list: "list",
    str: "str",
    tuple: "list",
}
_STR_TO_TYPE = {
    "bool": ConfigBool,
    "date": ConfigDate,
    "dict": ConfigDict,
    "list": ConfigList,
    "float": float,
    "int": int,
    "str": str,
}
_TYPE_SEPARATOR = ":"


class Plugin(
    openpaperwork_core.PluginBase,
    BugReportAttachment,
    ConfigBackend,
):
    TEST_FILE_URL = None  # unit tests only

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_core.fs.python'],
            ),
            openpaperwork_core.Dependency(
                interface=Paths,
                defaults=['openpaperwork_core.paths.xdg'],
            ),
        ]

    def __init__(self, core, config_path=None, base_path=None):
        super().__init__(core)
        self.config = configparser.RawConfigParser()
        self.application_name = None
        self.config_path = config_path
        self.observers = collections.defaultdict(set)
        self.default_plugins = []
        if base_path is not None:
            self.base_path = base_path
        else:
            self.base_path = self.core.call_success(Paths.paths_get_config_dir)

    def _set_config_path(self):
        if self.config_path is None:
            self.config_path = self.core.call_success(
                Fs.fs_join, self.base_path, self.application_name + ".conf"
            )

    def config_backend_load(self, application_name):
        self.application_name = application_name
        self._set_config_path()
        self.config = configparser.RawConfigParser()
        LOGGER.info("Loading configuration '%s' ...", self.config_path)
        if self.core.call_success(Fs.fs_exists, self.config_path) is not None:
            fd = self.core.call_success(Fs.fs_open, self.config_path, 'r')
            with fd:
                self.config.read_file(fd)
        else:
            LOGGER.warning(
                "Cannot load configuration '%s'. File does not exist",
                self.config_path
            )
        for observers in self.observers.values():
            for observer in observers:
                observer()

    def config_backend_save(self, application_name=None):
        if application_name is not None:
            self.application_name = application_name
        self._set_config_path()
        LOGGER.info("Writing configuration '%s' ...", self.config_path)
        with self.core.call_success(Fs.fs_open, self.config_path, 'w') as fd:
            self.config.write(fd)

    def config_backend_load_plugins(self, opt_name, default=[]):
        """
        Load and init the plugin list from the configuration.
        """
        self.default_plugins = default
        modules = self.config_backend_get(
            "plugins", opt_name, ConfigList(None, self.default_plugins)
        )
        LOGGER.info(
            "Loading and initializing plugins from configuration: %s",
            str(modules)
        )
        for module in modules:
            self.core.load(module)
        self.core.init()

    def config_backend_list_active_plugins(self, opt_name):
        return self.config_backend_get(
            "plugins", opt_name, ConfigList(None, self.default_plugins)
        )

    def config_backend_reset_plugins(self, opt_name):
        self.config_backend_del("plugins", opt_name)

    def config_backend_add_plugin(self, opt_name, module_name):
        LOGGER.info("Adding plugin '%s' to configuration", module_name)
        modules = self.config_backend_list_active_plugins(opt_name)
        modules.append(module_name)
        self.config_backend_put("plugins", opt_name, modules)

    def config_backend_remove_plugin(self, opt_name, module_name):
        LOGGER.info("Removing plugin '%s' from configuration", module_name)
        modules = self.config_backend_list_active_plugins(opt_name)
        try:
            modules.remove(module_name)
        except ValueError:
            LOGGER.warning("Plugin '%s' not found", module_name)
        self.config_backend_put("plugins", opt_name, modules)

    def config_backend_put(self, section, key, value):
        """
        Section must be a string.
        Key must be a string.
        """
        LOGGER.debug("Configuration: %s:%s <-- %s", section, key, str(value))
        if value is None:
            if section not in self.config:
                return
            if key not in self.config[section]:
                return
            self.config[section].pop(key)
            return
        t_str = _TYPE_TO_STR[type(value)]
        t = _STR_TO_TYPE[t_str]
        value = t(value)
        value = "{}{}{}".format(t_str, _TYPE_SEPARATOR, str(value))
        if section not in self.config:
            self.config[section] = {key: value}
        else:
            self.config[section][key] = value

        for observer in self.observers[section]:
            observer()

    def config_backend_del(self, section, key):
        if section not in self.config:
            return
        if key not in self.config[section]:
            return
        self.config.remove_option(section, key)

    def config_backend_get(self, section, key, default=None):
        try:
            value = self.config[section][key]
            if value.strip() == "":
                return None
            (t, value) = value.split(_TYPE_SEPARATOR, 1)
            r = _STR_TO_TYPE[t](value)
            if hasattr(r, 'get_value'):
                r = r.get_value()
            LOGGER.debug("Configuration: %s:%s --> %s", section, key, str(r))
            return r
        except KeyError:
            LOGGER.debug(
                "Configuration: %s:%s --> %s (default value)",
                section, key, str(default)
            )
            return default

    def config_backend_add_observer(self, section, callback):
        self.observers[section].add(callback)

    def config_backend_remove_observer(self, section, callback):
        self.observers[section].remove(callback)

    def bug_report_get_attachments(self, out: dict):
        if self.config_path is None:
            return
        if self.core.call_success(Fs.fs_exists, self.config_path) is None:
            return
        out['config'] = {
            'include_by_default': True,
            'date': None,
            'file_type': _("App. config."),
            'file_url': self.config_path,
            'file_size': self.core.call_success(Fs.fs_getsize, self.config_path)
        }
