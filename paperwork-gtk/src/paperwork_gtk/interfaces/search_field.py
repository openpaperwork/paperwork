import abc


class SearchResultsListener(abc.ABC):
    @abc.abstractmethod
    def on_search_start(self, query):
        ...

    @abc.abstractmethod
    def on_search_results(self, query, docs):
        ...


class Search(abc.ABC):
    @abc.abstractmethod
    def search_update_document_list(self, _=None):
        ...

    @abc.abstractmethod
    def search_by_keywords(self, query):
        ...

    @abc.abstractmethod
    def search_stop(self):
        ...


class SearchField(abc.ABC):
    @abc.abstractmethod
    def search_get(self):
        ...

    @abc.abstractmethod
    def search_set(self, text):
        ...

    @abc.abstractmethod
    def search_focus(self):
        ...

    @abc.abstractmethod
    def search_field_add(self, widget):
        ...
