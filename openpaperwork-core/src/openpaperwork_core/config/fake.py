import logging

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Setting(object):
    def __init__(self, value, default_func):
        self.value = value
        self.default_value_func = default_func
        self.observers = []

    def get(self):
        if self.value is None:
            return self.default_value_func()
        return self.value

    def put(self, v):
        self.value = v
        for obs in self.observers:
            obs()

    def add_observer(self, obs):
        self.observers.append(obs)

    def remove_observer(self, obs):
        self.observers.remove(obs)


class Plugin(PluginBase):
    """
    Translate values from the configuration into more usable ones.
    Provides default values (except for plugins).
    """
    @classmethod
    def get_interfaces(cls):
        return ['config']

    @classmethod
    def get_deps(cls):
        return []

    def __init__(self, core):
        super().__init__(core)
        self._settings = {}

    def __get_settings(self):
        return {k: v.get() for (k, v) in self._settings.items()}

    def __set_settings(self, new_settings):
        self._settings = {
            k: Setting(v, lambda: None)
            for (k, v) in new_settings.items()
        }

    settings = property(__get_settings, __set_settings)

    def config_load(self):
        pass

    def config_load_plugins(self, plugin_list_name, default_plugins=[]):
        pass

    def config_save(self):
        pass

    def config_build_simple(self, section, token, default):
        return Setting(None, default)

    def config_register(self, key, setting):
        if key not in self._settings:  # don't smash test settings
            self._settings[key] = setting

    def config_get_setting(self, key):
        return self._settings[key]

    def config_get(self, key):
        return self._settings[key].get()

    def config_get_default(self, key):
        return self._settings[key].default_value_func()

    def config_put(self, key, value):
        self._settings[key].put(value)

    def config_add_plugin(self, plugin):
        raise NotImplementedError()

    def config_remove_plugin(self, plugin):
        raise NotImplementedError()

    def config_list_plugins(self):
        raise NotImplementedError()

    def config_add_observer(self, key: str, callback):
        self._settings[key].add_observer(callback)

    def config_remove_observer(self, key: str, callback):
        self._settings[key].remove_observer(callback)
