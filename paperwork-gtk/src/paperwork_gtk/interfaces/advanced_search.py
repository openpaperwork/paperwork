import abc


class AdvancedSearchDialog(abc.ABC):
    @abc.abstractmethod
    def gtk_open_advanced_search_dialog(self):
        pass

    @abc.abstractmethod
    def gtk_close_advanced_search_dialog(self):
        pass
