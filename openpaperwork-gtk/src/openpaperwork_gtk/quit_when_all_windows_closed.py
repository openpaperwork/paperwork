import logging

from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.util

from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    GtkWindowListener,
    metaclass=openpaperwork_core.util.Singleton
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=['openpaperwork_gtk.mainloop.glib'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.nb_windows = 0

    def on_gtk_window_opened(self, window):
        self.nb_windows += 1

    def on_gtk_window_closed(self, window):
        self.nb_windows -= 1
        if self.nb_windows < 0:
            raise AssertionError()
        if self.nb_windows > 0:
            return
        self.core.call_success(Mainloop.mainloop_quit_graceful)
