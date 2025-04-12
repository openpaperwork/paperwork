import abc


class MainloopListener(abc.ABC):
    @abc.abstractmethod
    def on_mainloop_start(self):
        ...

    @abc.abstractmethod
    def on_mainloop_quit_graceful_request(self):
        ...

    @abc.abstractmethod
    def on_mainloop_quit(self):
        ...


class Mainloop(abc.ABC):
    @abc.abstractmethod
    def mainloop(self, halt_on_uncaught_exception=True, log_uncaught=True):
        ...

    @abc.abstractmethod
    def mainloop_get_thread_id(self):
        ...

    @abc.abstractmethod
    def mainloop_quit_graceful(self):
        ...

    @abc.abstractmethod
    def mainloop_quit_now(self):
        ...

    @abc.abstractmethod
    def mainloop_ref(self, obj):
        """
        If you run a task independently from the main loop, you may want
        to increment the reference counter of the main loop so
        `mainloop_quit_graceful` does not interrupt the main loop while your
        task is still running.

        ThreadedPromise already takes care of incrementing and decrementing
        this reference counter.
        """
        ...

    @abc.abstractmethod
    def mainloop_unref(self, obj):
        ...

    @abc.abstractmethod
    def mainloop_schedule(self, func, *args, delay_s=0, **kwargs):
        ...

    @abc.abstractmethod
    def mainloop_execute(self, func, *args, **kwargs):
        ...
