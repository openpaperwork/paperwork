import abc


class ThreadManager(abc.ABC):
    @abc.abstractmethod
    def thread_start(self, func, *args, **kwargs):
        ...
