import abc


class LogManager(abc.ABC):
    @abc.abstractmethod
    def init_logs(self, app_name, default_log_level):
        ...

    @abc.abstractmethod
    def set_log_level(self, log_level):
        ...


class LogArchiver(abc.ABC):
    pass
