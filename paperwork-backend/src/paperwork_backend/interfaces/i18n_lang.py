import abc


class I18nLang(abc.ABC):
    @abc.abstractmethod
    def i18n_lang_iso639_3_to_full(self, iso):
        ...
