import abc


class StatsPost(abc.ABC):
    @abc.abstractmethod
    def stats_send(self):
        ...
