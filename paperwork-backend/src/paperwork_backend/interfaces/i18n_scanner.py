import abc


class I18nScanner(abc.ABC):
    @abc.abstractmethod
    def i18n_scanner_source(self, source_name):
        ...
