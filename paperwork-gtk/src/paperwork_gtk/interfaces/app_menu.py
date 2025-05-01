import abc


class AppMenu(abc.ABC):
    @abc.abstractmethod
    def menu_app_append_item(self, item):
        ...

    @abc.abstractmethod
    def menu_app_append_submenu(self, label, menu):
        ...

    @abc.abstractmethod
    def screenshot_snap_doc_action_menu(self, out_file):
        ...
