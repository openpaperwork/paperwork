import abc


class SyncListener(abc.ABC):
    @abc.abstractmethod
    def on_sync(name, status, key):
        ...


class Syncable(abc.ABC):
    @abc.abstractmethod
    def sync(self, promises: list):
        ...


class DocTracker(abc.ABC):
    @abc.abstractmethod
    def doc_tracker_register(self, name, transaction_factory):
        ...

    @abc.abstractmethod
    def doc_tracker_get_all_doc_ids(self):
        ...

    @abc.abstractmethod
    def doc_tracker_get_doc_text_by_id(self, doc_id):
        ...


class AbstractPageTracker(abc.ABC):
    @abc.abstractmethod
    def find_changes(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def ack_page(self, doc_id, doc_url, page_idx):
        """
        Mark the page update has handled.
        """
        ...

    @abc.abstractmethod
    def cancel(self):
        ...

    @abc.abstractmethod
    def commit(self):
        ...

    @abc.abstractmethod
    def delete_doc(self, doc_id):
        ...


class PageTracker(abc.ABC):
    @abc.abstractmethod
    def page_tracker_get(self, tracking_id) -> AbstractPageTracker:
        ...
