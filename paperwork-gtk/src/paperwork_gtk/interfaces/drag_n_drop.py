import abc


class DragAndDropDestination(abc.ABC):
    @abc.abstractmethod
    def drag_and_drop_get_destination(self, widget, x, y):
        ...


class DragAndDrop(abc.ABC):
    @abc.abstractmethod
    def drag_and_drop_page_enable(self, widget):
        """
        Arguments:
            widget - GTK widget on which page drag'n'drop must be enabled.

        When a drop is received, it will call the method
        'drag_and_drop_get_destination(widget, x, y)'.
        The plugin to whom the widget belongs should reply with
        (doc_id, page_idx).
        """
        ...

    @abc.abstractmethod
    def drag_and_drop_page_add(self, src_uri, dst_doc_id, dst_doc_url, dst_page_idx):
        ...

    @abc.abstractmethod
    def drag_and_drop_apply(self):
        ...
