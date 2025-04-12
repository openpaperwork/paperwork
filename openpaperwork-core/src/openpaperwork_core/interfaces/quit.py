import abc


class QuitListener(abc.ABC):
    @abc.abstractmethod
    def on_quit(self):
        ...
