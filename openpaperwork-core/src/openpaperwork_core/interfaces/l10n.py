import abc


class L10nInit(abc.ABC):
    pass


class L10n(abc.ABC):
    @abc.abstractmethod
    def l10n_load(self, python_package, text_domain):
        ...
