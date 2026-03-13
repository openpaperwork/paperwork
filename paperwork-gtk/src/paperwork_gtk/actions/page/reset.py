import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.pages import PageManagement

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_viewer import (
    DocViewer,
    PageViewerListener
)


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_reset"


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
                interface=PageManagement,
                defaults=['paperwork_backend.model.img_overlay'],
            ),
            openpaperwork_core.Dependency(
                interface=DocOpener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=DocViewer,
                defaults=[],
            ),
            openpaperwork_core.Dependency(
                interface=DocTransactionManager,
                defaults=['paperwork_backend.sync'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=["openpaperwork_gtk.mainloop.glib"],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        self.active_doc = None
        self.active_page_idx = -1

        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._reset)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_reload(self):
        pass

    def doc_close(self):
        self.active_doc = None

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _reset(self, *args, **kwargs):
        assert self.active_doc is not None

        (doc_id, doc_url) = self.active_doc
        page_idx = self.active_page_idx

        LOGGER.info("Will reset page %s p%d", doc_id, page_idx)

        self.core.call_all(PageManagement.page_reset_by_url, doc_url, page_idx)
        self.core.call_all(DocOpener.doc_reload, doc_id, doc_url)
        self.core.call_success(
            Mainloop.mainloop_schedule, self.core.call_all, DocViewer.doc_goto_page, page_idx
        )
        self.core.call_success(DocTransactionManager.transaction_simple, [("upd", doc_id),])

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
