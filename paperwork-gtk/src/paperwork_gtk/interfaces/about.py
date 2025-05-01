import abc


class GtkAbout(abc.ABC):
    @abc.abstractmethod
    def gtk_open_about(self):
        ...
