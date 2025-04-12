#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2025 Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.
"""
Paperwork configuration management code
"""

import collections
import logging

from openpaperwork_core import PluginBase
from openpaperwork_core.interfaces.app import App
from openpaperwork_core.interfaces.config import AbstractSetting
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.config_backend import ConfigBackend


LOGGER = logging.getLogger(__name__)


class Setting(AbstractSetting):
    def __init__(self, core, section, token, default_value_func):
        self.core = core
        self.section = section
        self.token = token
        self.default_value_func = default_value_func

    def get(self):
        value = self.core.call_success(
            ConfigBackend.config_backend_get, self.section, self.token, None
        )
        if value is None:
            return self.default_value_func()
        else:
            return value

    def put(self, value):
        self.core.call_all(
            ConfigBackend.config_backend_put, self.section, self.token, value
        )


class Plugin(
    PluginBase,
    Config
):
    """
    Translate values from the configuration into more usable ones.
    Provides default values (except for plugins).
    """

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': App,
                'defaults': ['openpaperwork_core.app'],
            },
            {
                'interface': ConfigBackend,
                'defaults': ['openpaperwork_core.config.backend.configparser'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.settings = {}
        self.values = {}
        # applicatiom here is a bit more specific: paperwork-gtk,
        # paperwork-shell, etc.
        # It is used to known which plugin list must be loaded
        self.plugin_list_name = None
        self.observers = collections.defaultdict(set)
        self.settings = {}

    def config_load(self):
        application = self.core.call_success(App.app_get_fs_name)
        LOGGER.info("Loading configuration for %s", application)

        self.values = {}
        self.core.call_all(ConfigBackend.config_backend_load, application)
        for observers in self.observers.values():
            for observer in observers:
                observer()

    def config_load_plugins(self, plugin_list_name, default_plugins=[]):
        LOGGER.info("Loading plugins for '%s'", plugin_list_name)
        self.plugin_list_name = plugin_list_name
        self.core.call_all(
            ConfigBackend.config_backend_load_plugins,
            plugin_list_name, default_plugins
        )

    def config_get_plugin_list_name(self):
        return self.plugin_list_name

    def config_save(self):
        LOGGER.info("Saving configuration")
        self.core.call_all(ConfigBackend.config_backend_save)

    def config_build_simple(
                self, section, token, default_value_func
            ):
        """
        Provide a default simple implementation for a new setting that can
        be registered using 'config_register'.

        Arguments:
          - section: Section in which option must be stored (see ConfigParser)
          - token: token name for the option (see ConfigParser)
          - default_value_func: function to call to get the default value if
            none is stored in the file.
        """
        return Setting(self.core, section, token, default_value_func)

    def config_register(self, key: str, setting):
        """
        Add another setting to manage. Make this setting available to other
        components.

        Arguments:
          - key: configuration key
          - setting: Setting must be an object providing a method `get()`
            and a method `put(value)`. See :func:`config_build_simple` to
            get quickly a default implementation.
        """
        LOGGER.debug("Registering configuration: %s", key)
        self.settings[key] = setting

    def config_list_options(self):
        return list(self.settings.keys())

    def config_get_setting(self, key: str):
        return self.settings[key]

    def config_get(self, key: str):
        LOGGER.debug("Config get: %s", key)
        if key not in self.settings:
            return None
        if key not in self.values:
            self.values[key] = self.settings[key].get()
        return self.values[key]

    def config_get_default(self, key: str):
        return self.settings[key].default_value_func()

    def config_put(self, key: str, value):
        """
        Store a setting value.
        Warning: You must call :func:`config_save` so the changes are actually
        saved.

        Arguments:
          - key: configuration key,
          - value: can be of many types (`str`, `int`, etc).
        """
        LOGGER.debug("Config put: %s", key)
        self.settings[key].put(value)
        self.values[key] = value
        if key in self.observers:
            for callback in self.observers[key]:
                callback()

    def config_add_plugin(self, plugin, plugin_list_name=None):
        if plugin_list_name is None:
            plugin_list_name = self.plugin_list_name
        LOGGER.debug("Config add plugin: %s -> %s", plugin, plugin_list_name)
        self.core.call_all(
            ConfigBackend.config_backend_add_plugin, plugin_list_name, plugin
        )

    def config_remove_plugin(self, plugin, plugin_list_name=None):
        if plugin_list_name is None:
            plugin_list_name = self.plugin_list_name
        LOGGER.debug(
            "Config remove plugin: %s -> %s",
            plugin, plugin_list_name
        )
        self.core.call_all(
            ConfigBackend.config_backend_remove_plugin, plugin_list_name, plugin
        )

    def config_list_plugins(self, plugin_list_name=None):
        if plugin_list_name is None:
            plugin_list_name = self.plugin_list_name
        return self.core.call_success(
            ConfigBackend.config_backend_list_active_plugins, plugin_list_name
        )

    def config_reset_plugins(self, plugin_list_name=None):
        if plugin_list_name is None:
            plugin_list_name = self.plugin_list_name
        LOGGER.debug("Config reset plugin: %s", plugin_list_name)
        return self.core.call_success(
            ConfigBackend.config_backend_reset_plugins, plugin_list_name
        )

    def config_add_observer(self, key: str, callback):
        self.observers[key].add(callback)

    def config_remove_observer(self, key: str, callback):
        self.observers[key].remove(callback)
