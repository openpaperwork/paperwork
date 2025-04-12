import abc


class Perfcheck(abc.ABC):
    @abc.abstractmethod
    def on_perfcheck_start(self, task_name):
        ...

    @abc.abstractmethod
    def on_perfcheck_stop(self, task_name, **extras):
        ...
