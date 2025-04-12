import logging

from openpaperwork_core.interfaces.mainloop import Mainloop


LOGGER = logging.getLogger(__name__)


class Task(object):
    def __init__(self, core, func, args, kwargs):
        self.core = core
        self.func = func
        self.args = args
        self.kwargs = kwargs
        # The mainloop can't track other threads, but if there is
        # a graceful shutdown waiting, we don't want it to stop the main
        # loop before our thread is done.
        # --> increment mainloop ref counter before
        core.call_all(Mainloop.mainloop_ref, self)

    def __str__(self):
        return "Task<{}>({}, {})".format(self.func, self.args, self.kwargs)

    def __repr__(self):
        return str(self)

    def do(self):
        try:
            self.func(*self.args, **self.kwargs)
        except Exception as exc:
            LOGGER.error(
                "==== UNCAUGHT EXCEPTION IN THREAD ===", exc_info=exc
            )
        finally:
            self.core.call_all(Mainloop.mainloop_unref, self)
