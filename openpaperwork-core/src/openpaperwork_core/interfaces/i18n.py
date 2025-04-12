import abc


class I18n(abc.ABC):
    @abc.abstractmethod
    def i18n_date_short(self, date):
        ...

    @abc.abstractmethod
    def i18n_parse_date_short(self, txt):
        ...

    @abc.abstractmethod
    def i18n_date_long_year(self, date):
        ...

    @abc.abstractmethod
    def i18n_date_long_month(self, date):
        ...

    @abc.abstractmethod
    def i18n_file_size(self, num):
        ...

    @abc.abstractmethod
    def i18n_strip_accents(self, string):
        ...

    @abc.abstractmethod
    def i18n_sort(self, string_list):
        ...
