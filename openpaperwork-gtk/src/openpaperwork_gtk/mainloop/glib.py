import faulthandler
import logging
import sys
import threading

try:
    from gi.repository import GLib
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False


import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.util

LOGGER = logging.getLogger(__name__)


class Plugin(
            openpaperwork_core.PluginBase,
            metaclass=openpaperwork_core.util.Singleton
        ):
    """
    A main loop based on GLib's mainloop.
    See `openpaperwork_core.mainloop.asyncio` for doc.
    """

    PRIORITY = 1000

    @classmethod
    def get_interfaces(cls):
        return [
            "chkdeps",
            "mainloop",
        ]

    def __init__(self, core):
        super().__init__(core)
        self.halt_on_uncaught_exception = True
        self.log_uncaught = True
        self.loop = None
        self.loop_ident = None
        self.halt_cause = None
        self.task_count = 0
        self.lock = threading.RLock()

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _check_mainloop_instantiated(self):
        if self.loop is None:
            self.loop = GLib.MainLoop.new(None, False)  # !running

    def mainloop(self, halt_on_uncaught_exception=True, log_uncaught=True):
        if not GLIB_AVAILABLE:
            return None

        self._check_mainloop_instantiated()
        self.log_uncaught = log_uncaught
        self.halt_on_uncaught_exception = halt_on_uncaught_exception

        self.loop_ident = threading.current_thread().ident

        self.mainloop_schedule(self.core.call_all, "on_mainloop_start")

        try:
            self.loop.run()
        except Exception:
            faulthandler.dump_traceback()
            raise
        finally:
            self.loop_ident = None

        self.core.call_all("on_mainloop_quit")

        if self.halt_cause is not None:
            halt_cause = self.halt_cause
            self.halt_cause = None
            LOGGER.error("Main loop stopped because %s", str(halt_cause))
            raise halt_cause

        self.loop = None
        return True

    def mainloop_get_thread_id(self):
        return self.loop_ident

    def mainloop_quit_graceful(self):
        self.mainloop_schedule(self._mainloop_quit_graceful)
        return True

    def _mainloop_quit_graceful(self):
        quit_now = True

        with self.lock:
            # keep in mind this function is in a task too
            if self.task_count > 1:
                quit_now = False
                LOGGER.info(
                    "Quit graceful: Remaining tasks: %d", self.task_count - 1
                )

        if not quit_now:
            self.mainloop_schedule(
                self._mainloop_quit_graceful, delay_s=0.2
            )
            return

        LOGGER.info("Quit graceful: Quitting")

        self.mainloop_quit_now()

        with self.lock:
            self.task_count = 1  # we are actually the one task still running

    def mainloop_quit_now(self):
        if self.loop is None:
            return None

        with self.lock:
            self.loop.quit()
            self.loop = None
            self.task_count = 0

    def mainloop_ref(self, obj):
        with self.lock:
            self.task_count += 1

    def mainloop_unref(self, obj):
        with self.lock:
            self.task_count -= 1
            assert self.task_count >= 0

    def mainloop_schedule(self, func, *args, delay_s=0, **kwargs):
        if not GLIB_AVAILABLE:
            return None

        assert hasattr(func, '__call__')

        with self.lock:
            self._check_mainloop_instantiated()

            self.task_count += 1

        def decorator(func, args):
            (args, kwargs) = args
            try:
                func(*args, **kwargs)
            except Exception as exc:
                exc_info = sys.exc_info()
                if self.halt_on_uncaught_exception:
                    LOGGER.error(
                        "Main loop: uncaught exception (%s) ! Quitting",
                        func, exc_info=exc
                    )
                    self.halt_cause = exc
                    self.mainloop_quit_now()
                elif self.log_uncaught:
                    LOGGER.error(
                        "Main loop: uncaught exception (%s) !",
                        func, exc_info=exc
                    )
                self.core.call_all(
                    "mainloop_schedule",
                    self.core.call_all, "on_uncaught_exception", exc_info
                )
            finally:
                with self.lock:
                    self.task_count -= 1
            return False

        args = (args, kwargs)

        if delay_s is None:
            GLib.idle_add(decorator, func, args, priority=GLib.PRIORITY_LOW)
        else:
            GLib.timeout_add(delay_s * 1000, decorator, func, args)
        return True

    def mainloop_execute(self, func, *args, **kwargs):
        current = threading.current_thread().ident

        # XXX(Jflesch):
        # if self.loop_ident is None, it means the mainloop hasn't been started
        # yet --> we cannot run the function on the mainloop anyway, so
        # we assume we are on the same thread that will later run the main
        # loop.
        if self.loop_ident is None or current == self.loop_ident:
            return func(*args, **kwargs)

        event = threading.Event()
        out = None
        exc = None

        def get_result():
            nonlocal out
            nonlocal exc
            try:
                out = func(*args, **kwargs)
            except Exception as e:
                LOGGER.warning(
                    "mainloop_execute exception (func=%s, args=%s, kwargs=%s)",
                    func, args, kwargs, exc_info=e
                )
                exc = e
            event.set()

        self.mainloop_schedule(get_result)
        event.wait()

        if exc is not None:
            raise exc
        return out
