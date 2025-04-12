import abc


class UncaughtExceptionListener(abc.ABC):
    @abc.abstractmethod
    def on_uncaught_exception(self, exc_info):
        ...


class UncaughtExceptionCatcher(abc.ABC):
    pass
