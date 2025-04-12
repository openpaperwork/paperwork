import abc


class ActivityListener(abc.ABC):
    @abc.abstractmethod
    def on_busy(self):
        ...

    @abc.abstractmethod
    def on_idle(self):
        ...
