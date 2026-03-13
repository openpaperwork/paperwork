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
from paperwork_gtk.interfaces.doc_viewer import PageViewerListener
from paperwork_gtk.interfaces.page_editor import PageEditor


LOGGER = logging.getLogger(__name__)


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
                interface=PageEditor,
                defaults=['paperwork_gtk.mainwindow.pageeditor'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = None
        self.active_page_idx = -1
        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new("page_edit", None)
        action.connect("activate", self._on_edit)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    @openpaperwork_core.noop
    def doc_close(self):
        pass

    def on_page_shown(self, page_idx):
        self.active_page = page_idx

    def _on_edit(self, *args, **kwargs):
        self.core.call_all(
            PageEditor.gtk_open_page_editor, *self.active_doc, self.active_page
        )

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
