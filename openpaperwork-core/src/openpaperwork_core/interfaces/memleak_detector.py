import abc


class MemleakDetector(abc.ABC):
    @abc.abstractmethod
    def on_objref_track(self, obj):
        ...

    @abc.abstractmethod
    def on_objref_graph(self):
        ...

    @abc.abstractmethod
    def on_memleak_track_stop(self):
        ...
