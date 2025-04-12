import abc


class ConfigBackend(abc.ABC):
    @abc.abstractmethod
    def config_backend_load(self, application_name):
        ...

    @abc.abstractmethod
    def config_backend_save(self, application_name=None):
        ...

    @abc.abstractmethod
    def config_backend_load_plugins(self, opt_name, default=[]):
        ...

    @abc.abstractmethod
    def config_backend_list_active_plugins(self, opt_name):
        ...

    @abc.abstractmethod
    def config_backend_reset_plugins(self, opt_name):
        ...

    @abc.abstractmethod
    def config_backend_add_plugin(self, opt_name, module_name):
        ...

    @abc.abstractmethod
    def config_backend_remove_plugin(self, opt_name, module_name):
        ...

    @abc.abstractmethod
    def config_backend_put(self, section, key, value):
        ...

    @abc.abstractmethod
    def config_backend_del(self, section, key):
        ...

    @abc.abstractmethod
    def config_backend_get(self, section, key, default=None):
        ...

    @abc.abstractmethod
    def config_backend_add_observer(self, section, callback):
        ...

    @abc.abstractmethod
    def config_backend_remove_observer(self, section, callback):
        ...
