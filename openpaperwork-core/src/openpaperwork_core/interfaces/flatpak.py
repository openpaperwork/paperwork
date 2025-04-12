import abc


class Flatpak(abc.ABC):
    @abc.abstractmethod
    def is_in_flatpak(self):
        ...
