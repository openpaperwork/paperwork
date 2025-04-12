import abc


class Stats(abc.ABC):
    @abc.abstractmethod
    def stats_get(self, out: dict):
        ...


class StatsListener(abc.ABC):
    @abc.abstractmethod
    def on_stats_sent(self):
        ...
