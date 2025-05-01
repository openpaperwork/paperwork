import abc


class HelpDocs(abc.ABC):
    @abc.abstractmethod
    def help_get_files(self):
        ...

    @abc.abstractmethod
    def help_get_file(self, name):
        ...

    @abc.abstractmethod
    def help_labels_get_all(self, out: set):
        ...


class HelpMenu(abc.ABC):
    @abc.abstractmethod
    def help_add_menu_item(self, menu_item):
        ...
