import logging

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.config_backend import ConfigBackend
import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Config,
):
    PRIORITY = 1000

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": ConfigBackend,
                "defaults": [],
            },
        ]

    @openpaperwork_core.noop
    def config_load(self):
        pass

    def config_load_plugins(self, plugin_list_name, default_plugins=[]):
        old_default = self.core.call_success(
            ConfigBackend.config_backend_get, "default_plugins", plugin_list_name, None
        )
        if old_default is None:
            # no previously known list of default plugins. Weird but not much
            # we can do about it.
            self.core.call_all(
                ConfigBackend.config_backend_put,
                "default_plugins", plugin_list_name, default_plugins
            )
            self.core.call_all(ConfigBackend.config_backend_save)
            return

        old_default = sorted(old_default)
        default_plugins = sorted(default_plugins)

        if old_default == default_plugins:
            # default list hasn't changed. So we assume the custom list
            # is still fine.
            return

        LOGGER.warning(
            "Default plugin list has changed."
            " Reseting plugin list to its new default."
        )
        LOGGER.warning("Old default list: %s", old_default)
        LOGGER.warning("New default list: %s", default_plugins)

        self.core.call_all(ConfigBackend.config_backend_reset_plugins, plugin_list_name)
        self.core.call_all(
            ConfigBackend.config_backend_put,
            "default_plugins", plugin_list_name, default_plugins
        )
        self.core.call_all(ConfigBackend.config_backend_save)

    @openpaperwork_core.noop
    def config_get_plugin_list_name(self):
        pass

    @openpaperwork_core.noop
    def config_save(self):
        pass

    @openpaperwork_core.noop
    def config_build_simple(
        self, section: str, token: str, default_value_func,
    ):
        pass

    @openpaperwork_core.noop
    def config_register(self, key: str, setting):
        pass

    @openpaperwork_core.noop
    def config_list_options(self):
        pass

    @openpaperwork_core.noop
    def config_get_setting(self, key: str):
        pass

    @openpaperwork_core.noop
    def config_get(self, key: str):
        pass

    @openpaperwork_core.noop
    def config_get_default(self, key: str):
        pass

    @openpaperwork_core.noop
    def config_put(self, key: str, value):
        pass

    @openpaperwork_core.noop
    def config_add_plugin(self, plugin, plugin_list_name=None):
        pass

    @openpaperwork_core.noop
    def config_remove_plugin(self, plugin, plugin_list_name=None):
        pass

    @openpaperwork_core.noop
    def config_list_plugins(self, plugin_list_name=None):
        pass

    @openpaperwork_core.noop
    def config_reset_plugins(self, plugin_list_name=None):
        pass

    @openpaperwork_core.noop
    def config_add_observer(self, key: str, callback):
        pass

    @openpaperwork_core.noop
    def config_remove_observer(self, key: str, callback):
        pass
