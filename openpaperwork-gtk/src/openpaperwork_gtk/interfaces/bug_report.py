import abc


class GtkBugReportBuilder(abc.ABC):
    @abc.abstractmethod
    def build_gtk_bug_report(self, widget_tree):
        ...

    @abc.abstractmethod
    def bug_report_set_file_urls_to_send(self, file_urls):
        ...


class GtkBugReportDisplay(abc.ABC):
    @abc.abstractmethod
    def open_bug_report(self):
        ...

    @abc.abstractmethod
    def close_bug_report(self):
        ...

    @abc.abstractmethod
    def bug_report_add_method(
        self, title, description,
        enable_callback, disable_callback,
        widget_tree
    ):
        ...
