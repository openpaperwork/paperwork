from typing import Callable

import abc


class AbstractSetting(abc.ABC):
    @abc.abstractmethod
    def get(self):
        ...

    @abc.abstractmethod
    def put(self, value):
        ...


class Config(abc.ABC):
    @abc.abstractmethod
    def config_load(self):
        ...

    @abc.abstractmethod
    def config_load_plugins(self, plugin_list_name, default_plugins=[]):
        ...

    @abc.abstractmethod
    def config_get_plugin_list_name(self):
        ...

    @abc.abstractmethod
    def config_save(self):
        ...

    @abc.abstractmethod
    def config_build_simple(
        self, section: str, token: str, default_value_func: Callable,
    ) -> AbstractSetting | None:
        ...

    @abc.abstractmethod
    def config_register(self, key: str, setting: AbstractSetting):
        ...

    @abc.abstractmethod
    def config_list_options(self):
        ...

    @abc.abstractmethod
    def config_get_setting(self, key: str):
        ...

    @abc.abstractmethod
    def config_get(self, key: str):
        ...

    @abc.abstractmethod
    def config_get_default(self, key: str):
        ...

    @abc.abstractmethod
    def config_put(self, key: str, value):
        ...

    @abc.abstractmethod
    def config_add_plugin(self, plugin, plugin_list_name=None):
        ...

    @abc.abstractmethod
    def config_remove_plugin(self, plugin, plugin_list_name=None):
        ...

    @abc.abstractmethod
    def config_list_plugins(self, plugin_list_name=None):
        ...

    @abc.abstractmethod
    def config_reset_plugins(self, plugin_list_name=None):
        ...

    @abc.abstractmethod
    def config_add_observer(self, key: str, callback):
        ...

    @abc.abstractmethod
    def config_remove_observer(self, key: str, callback):
        ...
