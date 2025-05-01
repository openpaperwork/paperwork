import abc


class DocPropertiesUpdate:
    def __init__(self, doc_id, multiple_docs=False):
        self.doc_id = doc_id
        self.multiple_docs = multiple_docs

        self.new_docs = set()
        self.upd_docs = set()
        self.del_docs = set()


class DocPropertiesComponent(abc.ABC):
    @abc.abstractmethod
    def doc_properties_components_get(self, out_components, multiple_docs: bool):
        ...

    @abc.abstractmethod
    def doc_properties_components_set_active_doc(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def doc_properties_components_set_active_docs(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def doc_properties_components_apply_changes(self, update: DocPropertiesUpdate):
        ...

    @abc.abstractmethod
    def doc_properties_components_cancel_changes(self):
        ...


class DocProperties(abc.ABC):
    @abc.abstractmethod
    def open_doc_properties(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def open_docs_properties(self, docs):
        ...

    @abc.abstractmethod
    def close_doc_properties(self):
        ...

    @abc.abstractmethod
    def docproperties_scroll_to_last(self):
        ...
