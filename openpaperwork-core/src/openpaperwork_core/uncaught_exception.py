import sys

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.uncaught_exception_listener import UncaughtExceptionCatcher
from openpaperwork_core.interfaces.uncaught_exception_listener import UncaughtExceptionListener
import openpaperwork_core


class Plugin(
    openpaperwork_core.PluginBase,
    UncaughtExceptionCatcher
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=['openpaperwork_core.mainloop.asyncio'],
            ),
            openpaperwork_core.Dependency(
                interface=UncaughtExceptionListener,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self._original_hook = sys.excepthook
        sys.excepthook = self._on_uncaught_exception

    def _on_uncaught_exception(self, exc_type, exc_instance, exc_tb):
        exc_info = (exc_type, exc_instance, exc_tb)
        try:
            self.core.call_one(
                Mainloop.mainloop_execute, self._broadcast_exception, exc_info
            )
        finally:
            if getattr(sys, 'frozen', False):
                # Assumes that cx_freeze has put a specific handler
                # for uncatched exceptions (popup and stuff)
                self._original_hook(exc_type, exc_instance, exc_tb)

    def _broadcast_exception(self, exc_info):
        # make sure we don't loop
        sys.excepthook = self._original_hook
        try:
            nb = self.core.call_all(UncaughtExceptionListener.on_uncaught_exception, exc_info)
            if nb <= 0:
                # no log handler yet --> switch back to default
                self._original_hook(*exc_info)
        finally:
            sys.excepthook = self._on_uncaught_exception
