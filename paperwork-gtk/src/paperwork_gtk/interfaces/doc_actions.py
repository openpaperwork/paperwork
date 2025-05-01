import abc


class DocActions(abc.ABC):
    @abc.abstractmethod
    def add_doc_action(self, action_label, action_name):
        ...

    @abc.abstractmethod
    def add_doc_main_action(self, icon_name, txt, callback):
        ...

    @abc.abstractmethod
    def docs_menu_append_item(self, item):
        ...

    @abc.abstractmethod
    def docs_menu_append_submenu(self, label, menu):
        ...
