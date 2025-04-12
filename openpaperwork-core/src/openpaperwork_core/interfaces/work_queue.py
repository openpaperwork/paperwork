import abc


class WorkQueue(abc.ABC):
    @abc.abstractmethod
    def work_queue_create(self, queue_name, stop_on_quit=False, hide_uncatched=False):
        ...

    @abc.abstractmethod
    def work_queue_add_promise(self, queue_name, promise, priority=0):
        ...

    @abc.abstractmethod
    def work_queue_cancel(self, queue_name, promise):
        ...

    @abc.abstractmethod
    def work_queue_cancel_all(self, queue_name):
        ...
