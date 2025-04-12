import abc


class GuiListener(abc.ABC):
    @abc.abstractmethod
    def on_gui_initialized(self):
        ...

    @abc.abstractmethod
    def new_mainwindow(self):
        ...
