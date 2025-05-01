from typing import Optional
import abc


class MainWindowListener(abc.ABC):
    @abc.abstractmethod
    def on_mainwindow_fold_change(self):
        ...


class MainWindow(abc.ABC):
    @abc.abstractmethod
    def mainwindow_get_folded(self):
        ...

    @abc.abstractmethod
    def mainwindow_add(self, side: str, name: str, prio: int, header, body):
        ...

    @abc.abstractmethod
    def mainwindow_show(self, side: str, name: Optional[str] = None):
        ...

    @abc.abstractmethod
    def mainwindow_show_default(self, side: str):
        ...

    @abc.abstractmethod
    def mainwindow_back(self, side: str):
        ...

    @abc.abstractmethod
    def mainwindow_focus(self):
        ...
