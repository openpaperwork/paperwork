from typing import List
import abc


class AbstractDocTransaction(abc.ABC):
    @abc.abstractmethod
    def add_doc(self, doc_id):
        ...

    @abc.abstractmethod
    def upd_doc(self, doc_id):
        ...

    @abc.abstractmethod
    def del_doc(self, doc_id):
        ...

    @abc.abstractmethod
    def unchanged_doc(self, doc_id):
        ...

    @abc.abstractmethod
    def cancel(self):
        ...

    @abc.abstractmethod
    def commit(self):
        ...


class DocTransactionFactory(abc.ABC):
    @abc.abstractmethod
    def doc_transaction_start(
        self,
        out_transactions: List[AbstractDocTransaction],
        nb_changes: int
    ):
        ...


class DocTransactionManager(abc.ABC):
    @abc.abstractmethod
    def transaction_schedule(self, promise):
        ...

    @abc.abstractmethod
    def transaction_simple_promise(self, changes):
        ...

    @abc.abstractmethod
    def transaction_simple(self, changes: list):
        ...

    @abc.abstractmethod
    def transaction_sync_all(self):
        ...
