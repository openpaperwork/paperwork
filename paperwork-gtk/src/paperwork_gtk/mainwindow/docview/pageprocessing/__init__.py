"""
Wraps a pageview in a GtkOverlay + GtkSpinner. Displays the spinner
on top of the pageview when another plugin is working on the page.
"""

import logging

try:
    from gi.repository import GObject
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

    # workaround so chkdeps can still be called
    class GObject(object):
        TYPE_BOOLEAN = 0

        class SignalFlags(object):
            RUN_LAST = 0

        class GObject(object):
            pass

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.page_modification import PageModificationListener

from paperwork_gtk.interfaces.doc_viewer import DocViewerComponentFactory


LOGGER = logging.getLogger(__name__)


class PageWrapper(GObject.GObject):
    __gsignals__ = {
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'visibility_changed': (GObject.SignalFlags.RUN_LAST, None, (
            GObject.TYPE_BOOLEAN,
        )),
    }

    def __init__(self, plugin, page):
        super().__init__()
        self.plugin = plugin
        self.page = page
        self.page_idx = page.page_idx
        self.busy = False

        self.widget_tree = self.plugin.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docview.pageprocessing",
            "pageprocessing.glade",
        )
        self.widget = self.widget_tree.get_object("pageprocessing_overlay")

        self.widget.add(page.widget)

        page.connect("getting_size", lambda p: self.emit('getting_size'))
        page.connect("size_obtained", lambda p: self.emit("size_obtained"))
        page.connect("img_obtained", lambda p: self.emit("img_obtained"))
        page.connect(
            "visibility_changed",
            lambda p, v: self.emit("visibility_changed", v)
        )

        page.widget.connect("draw", self._on_draw)

    def load(self):
        self.page.load()

    def close(self):
        self.page.close()

    def get_zoom(self):
        return self.page.get_zoom()

    def set_zoom(self, zoom):
        return self.page.set_zoom(zoom)

    def get_full_size(self):
        return self.page.get_full_size()

    def get_size(self):
        return self.page.get_size()

    def resize(self):
        return self.page.resize()

    def refresh(self, reload=False):
        return self.page.refresh(reload=reload)

    def set_visible(self, visible):
        return self.page.set_visible(visible)

    def get_visible(self):
        return self.page.get_visible()

    def _on_draw(self, overlay, cairo_ctx):
        if not self.busy:
            return

        w = overlay.get_allocated_width()
        h = overlay.get_allocated_height()

        cairo_ctx.set_source_rgba(0.5, 0.5, 0.5, 0.5)
        cairo_ctx.rectangle(0, 0, w, h)
        cairo_ctx.fill()

    def on_page_modification_start(self):
        self.busy = True
        spinner = self.widget_tree.get_object("pageprocessing_spinner")
        spinner.set_visible(True)
        spinner.start()

    def on_page_modification_end(self):
        self.busy = False
        spinner = self.widget_tree.get_object("pageprocessing_spinner")
        spinner.set_visible(False)
        spinner.stop()
        self.page.refresh(reload=True)


if GLIB_AVAILABLE:
    GObject.type_register(PageWrapper)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocOpener,
    DocViewerComponentFactory,
    PageModificationListener,
):
    PRIORITY = -1000

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.wrappers = []
        self.active_doc_id = None
        self.active_pages = set()

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    @openpaperwork_core.noop
    def doc_open(self, doc_id, doc_url):
        pass

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def doc_close(self):
        self.wrappers = []

    def doc_open_components(self, out: list, doc_id, doc_url):
        if doc_id != self.active_doc_id:
            self.active_doc_id = doc_id
            self.active_pages = set()

        self.doc_close()

        # instantiate PageWrapper objects, and replace the pages in the
        # list 'out' by those wrappers.
        self.wrappers = [
            PageWrapper(self, page)
            for (visible, page) in out
        ]
        for page_idx in range(0, len(out)):
            out[page_idx] = (out[page_idx][0], self.wrappers[page_idx])
            if page_idx in self.active_pages:
                out[page_idx][1].on_page_modification_start()

    def on_page_modification_start(self, doc_id, page_idx):
        if doc_id != self.active_doc_id:
            return
        self.active_pages.add(page_idx)
        if page_idx >= len(self.wrappers):
            return
        self.wrappers[page_idx].on_page_modification_start()

    def on_page_modification_end(self, doc_id, page_idx):
        if doc_id != self.active_doc_id:
            return
        if page_idx in self.active_pages:
            self.active_pages.remove(page_idx)
        if page_idx >= len(self.wrappers):
            return
        self.wrappers[page_idx].on_page_modification_end()
