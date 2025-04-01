import sys

from . import PluginBase


class Plugin(PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['uncaught_exception']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.original_hook = sys.excepthook
        sys.excepthook = self._on_uncaught_exception

    def _on_uncaught_exception(self, exc_type, exc_instance, exc_tb):
        exc_info = (exc_type, exc_instance, exc_tb)
        try:
            self.core.call_one(
                "mainloop_execute", self._broadcast_exception, exc_info
            )
        finally:
            if getattr(sys, 'frozen', False):
                # Assumes that cx_freeze has put a specific handler
                # for uncatched exceptions (popup and stuff)
                self.original_hook(exc_type, exc_instance, exc_tb)

    def _broadcast_exception(self, exc_info):
        # make sure we don't loop
        sys.excepthook = self.original_hook
        try:
            nb = self.core.call_all("on_uncaught_exception", exc_info)
            if nb <= 0:
                # no log handler yet --> switch back to default
                self.original_hook(*exc_info)
        finally:
            sys.excepthook = self._on_uncaught_exception
