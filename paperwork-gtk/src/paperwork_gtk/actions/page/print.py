import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_print import DocPrint
from paperwork_gtk.interfaces.doc_viewer import PageViewerListener


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_print"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    DocOpener,
    PageViewerListener,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=AppActionCollector,
                defaults=['paperwork_gtk.mainwindow.window'],
            ),
            openpaperwork_core.Dependency(
                interface=DocPrint,
                defaults=['paperwork_gtk.print'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        self.active_doc = None
        self.active_page_idx = -1
        self.active_windows = []

        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._print)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def doc_close(self):
        self.active_doc = None

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _print(self, *args, **kwargs):
        assert self.active_doc is not None
        self.core.call_all(
            DocPrint.doc_print, *self.active_doc, [self.active_page_idx]
        )

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
