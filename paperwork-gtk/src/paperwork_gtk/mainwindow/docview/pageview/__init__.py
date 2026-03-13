import logging

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.memleak_detector import MemleakDetector
from openpaperwork_core.interfaces.perfcheck import Perfcheck
from openpaperwork_core.interfaces.progress import ProgressListener
from openpaperwork_core.interfaces.work_queue import WorkQueue
import openpaperwork_core
import openpaperwork_core.deps

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.screenshot import ScreenshotListener

from paperwork_backend.interfaces.cairo import CairoRendererFactory
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.pages import Pages

from paperwork_gtk.interfaces.doc_viewer import DocViewer, PageViewerListener
from paperwork_gtk.interfaces.doc_viewer import DocViewerComponentFactory
from paperwork_gtk.interfaces.page_drawer import PageDrawer

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

from paperwork_gtk import _


LOGGER = logging.getLogger(__name__)


class Page(GObject.GObject):
    __gsignals__ = {
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'visibility_changed': (GObject.SignalFlags.RUN_LAST, None, (
            GObject.TYPE_BOOLEAN,
        )),
    }

    def __init__(self, core, doc_id, doc_url, page_idx, nb_pages):
        super().__init__()
        self.core = core
        self.doc_id = doc_id
        self.doc_url = doc_url
        self.page_idx = page_idx
        self.nb_pages = nb_pages
        self.visible = False

        self.mtime = 0

        self.zoom = 1.0

        self.widget_tree = None
        self.widget = None
        self.renderer = None

        self._load_renderer()
        self.rebuild_widget()

    def _load_renderer(self):
        page_img_url = self.core.call_success(
            PageImg.page_get_img_url, self.doc_url, self.page_idx
        )
        LOGGER.info(
            "URL for %s p%d: %s", self.doc_url, self.page_idx, page_img_url
        )
        assert page_img_url is not None

        self.renderer = self.core.call_success(
            CairoRendererFactory.cairo_renderer_by_url, "page_loader", page_img_url
        )
        self.renderer.connect("getting_size", self._on_renderer_getting_size)
        self.renderer.connect("size_obtained", self._on_renderer_size)
        self.renderer.connect("img_obtained", self._on_renderer_img)

    def rebuild_widget(self):
        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docview.pageview", "pageview.glade"
        )
        self.widget = self.widget_tree.get_object("pageview_area")
        self.widget.set_visible(False)  # visible in the GTK sense
        self.widget.connect("draw", self._on_draw)
        self.resize()

    def __str__(self):
        return "{} p{}".format(self.doc_id, self.page_idx)

    def _on_renderer_getting_size(self, renderer):
        self.core.call_all(
            ProgressListener.on_progress, "loading_page_sizes",
            self.page_idx / self.nb_pages,
            _("Loading page {}/{} ...").format(self.page_idx, self.nb_pages)
        )
        self.emit('getting_size')

    def _on_renderer_size(self, renderer):
        LOGGER.info(
            "Page %d: size %d x %d",
            self.page_idx, self.renderer.size[0], self.renderer.size[1]
        )
        self.widget.set_visible(True)
        self.resize()
        self.core.call_all(PageViewerListener.on_page_size_obtained, self)
        self.emit('size_obtained')

    def _on_renderer_img(self, renderer):
        assert self.visible
        self.refresh()
        self.emit('img_obtained')

    def load(self):
        if not self.refresh(reload=True):
            # renderer has already loaded the page --> reemit the page size
            if self.renderer.size[0] != 0:
                self.core.call_success(
                    Mainloop.mainloop_schedule, self._on_renderer_size, self.renderer
                )

    def close(self):
        self.renderer.close()

    def get_zoom(self):
        return self.zoom

    def set_zoom(self, zoom):
        self.zoom = zoom
        self.resize()

    def get_full_size(self):
        return self.renderer.size

    def get_size(self):
        return (
            int(self.renderer.size[0] * self.zoom),
            int(self.renderer.size[1] * self.zoom)
        )

    def resize(self):
        if self.renderer.size[0] == 0:
            return
        self.renderer.zoom = self.zoom
        size = self.get_size()
        self.widget.set_size_request(size[0], size[1])

    def refresh(self, reload=False):
        if reload:
            # only if the mtime has changed. Otherwise there is no point.
            mtime = self.core.call_success(
                Pages.page_get_mtime_by_url, self.doc_url, self.page_idx
            )
            if self.mtime == mtime:
                reload = False
            else:
                self.mtime = mtime

        if reload:
            self.set_visible(False)
            self.close()
            self._load_renderer()
            self.renderer.start()
            return True
        elif self.widget is not None:
            self.widget.queue_draw()
            return False

    def hide(self):
        self.visible = False
        self.renderer.hide()
        self.core.call_all(PageDrawer.on_page_visibility_changed, self, False)
        self.emit('visibility_changed', False)

    def show(self):
        self.visible = True
        self.renderer.render()
        self.core.call_all(PageDrawer.on_page_visibility_changed, self, True)
        self.emit('visibility_changed', True)

    def set_visible(self, visible):
        if self.visible == visible:
            return

        if visible:
            self.show()
        else:
            self.hide()

    def get_visible(self):
        return self.visible

    def _on_draw(self, widget, cairo_ctx):
        self.renderer.draw(cairo_ctx)
        self.core.call_all(PageDrawer.on_page_draw, cairo_ctx, self)

    def blur(self):
        self.renderer.blur()
        self.widget.queue_draw()

    def unblur(self):
        self.renderer.unblur()
        self.widget.queue_draw()

    def detach_from_parent(self):
        parent = self.widget.get_parent()
        if parent is None:
            return
        parent.remove(self.widget)


if GLIB_AVAILABLE:
    GObject.type_register(Page)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocOpener,
    DocViewerComponentFactory,
    PageDrawer,
    ScreenshotListener,
):
    PRIORITY = 10000

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=CairoRendererFactory,
                defaults=[
                    'paperwork_backend.cairo.pillow',
                    'paperwork_backend.cairo.poppler',
                ],
            ),
            openpaperwork_core.Dependency(
                interface=Docs,
                defaults=[
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ],
            ),
            openpaperwork_core.Dependency(
                interface=DocViewer,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=MemleakDetector,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=PageImg,
                defaults=[
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            ),
            openpaperwork_core.Dependency(
                interface=Pages,
                defaults=[
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            ),
            openpaperwork_core.Dependency(
                interface=PageViewerListener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=Perfcheck,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=ProgressListener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=WorkQueue,
                defaults=['openpaperwork_core.work_queue.default'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.pages = []
        self.nb_to_load = 0
        self.active_doc = (None, None)
        self.core.call_all(
            WorkQueue.work_queue_create, "page_loader", stop_on_quit=True
        )

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
        self.core.call_success(WorkQueue.work_queue_cancel_all, "page_loader")
        for page in self.pages:
            page.close()
        self.pages = []

    def doc_open_components(self, out: list, doc_id, doc_url):
        active_doc = (doc_id, doc_url)
        if self.active_doc != active_doc:
            self.doc_close()
            self.active_doc = active_doc

        nb_pages = self.core.call_success(Docs.doc_get_nb_pages_by_url, doc_url)
        LOGGER.info("Number of pages displayed: %s", nb_pages)
        if nb_pages is None:
            LOGGER.warning("Failed to get the number of pages in %s", doc_id)
            nb_pages = 0

        self.core.call_all(MemleakDetector.on_objref_graph)

        self.core.call_all(
            Perfcheck.on_perfcheck_start,
            "pageview->doc_open_components({})".format(doc_id)
        )

        # drop the extra pages we have if any
        for page in self.pages[nb_pages:]:
            page.close()
        self.pages = self.pages[:nb_pages]

        # reuse the pages we already have to avoid useless refreshes
        for page in self.pages:
            page.detach_from_parent()

        # add any new page
        for page_idx in range(len(self.pages), nb_pages):
            self.pages.append(Page(
                self.core, doc_id, doc_url, page_idx, nb_pages
            ))

        LOGGER.info(
            "%d pages in the documents (%d components)",
            nb_pages, len(self.pages)
        )

        self.nb_to_load = len(self.pages)
        for page in self.pages:
            page.connect("size_obtained", self._on_page_img_size_obtained)
            out.append((True, page))

        self.core.call_all(
            Perfcheck.on_perfcheck_stop,
            "pageview->doc_open_components({})".format(doc_id),
            nb_pages=nb_pages
        )

    def _on_page_img_size_obtained(self, page):
        self.nb_to_load -= 1
        if self.nb_to_load > 0:
            return
        self.nb_to_load = 0
        self.core.call_all(ProgressListener.on_progress, "loading_page_sizes", 1.0)

    def pageview_refresh_all(self):
        for page in self.pages:
            page.refresh()

    @openpaperwork_core.noop
    def on_page_draw(self, cairo_ctx, page):
        pass

    @openpaperwork_core.noop
    def on_page_visibility_changed(self, page, visible):
        pass

    def on_screenshot_before(self):
        LOGGER.info("Blurring pages")
        for page in self.pages:
            page.blur()

    def on_screenshot_after(self):
        LOGGER.info("Unblurring pages")
        for page in self.pages:
            page.unblur()
