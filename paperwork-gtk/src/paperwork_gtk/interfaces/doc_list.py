import abc


class DocListListener(abc.ABC):
    @abc.abstractmethod
    def on_doclist_initialized(self):
        ...

    @abc.abstractmethod
    def on_doc_list_clear(self):
        ...

    @abc.abstractmethod
    def on_doc_box_creation(self, doc_id, row, flowlayout):
        ...

    @abc.abstractmethod
    def on_doc_list_visibility_changed(self):
        ...

    @abc.abstractmethod
    def on_doc_box_visible(self, doc_id, gtk_row, layout):
        ...


class DocList(abc.ABC):
    @abc.abstractmethod
    def doclist_add(self, widget, vposition):
        ...

    @abc.abstractmethod
    def doclist_clear(self):
        ...

    @abc.abstractmethod
    def doclist_extend(self, nb_docs):
        ...

    @abc.abstractmethod
    def doclist_show(self, docs, show_new=True):
        ...

    @abc.abstractmethod
    def doclist_menu_append_item(self, item):
        ...

    @abc.abstractmethod
    def doclist_menu_append_submenu(self, label, menu):
        ...

    @abc.abstractmethod
    def open_next_doc(self, offset: int):
        ...

    @abc.abstractmethod
    def doc_menu_open(self):
        ...


class DocSearch(abc.ABC):
    @abc.abstractmethod
    def search_refresh(self):
        ...
