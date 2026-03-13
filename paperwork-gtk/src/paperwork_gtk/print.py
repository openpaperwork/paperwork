import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.progress import ProgressListener
from openpaperwork_core.interfaces.work_queue import WorkQueue
import openpaperwork_core
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.cairo import Url2Cairo
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.pages import PageImg

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_print import DocPrint
from paperwork_gtk.interfaces.doc_viewer import PageViewerListener


DELAY = 0.1
LOGGER = logging.getLogger(__name__)


class SurfacePreloader:
    def __init__(self, core, doc_id, doc_url, page_indexes):
        self.core = core
        self.doc_id = doc_id
        self.doc_url = doc_url
        self.page_indexes = page_indexes
        self.page_surfaces = []

    def start(self):
        LOGGER.info("Will load %d pages", len(self.page_indexes))
        for (page_nb, page_idx) in enumerate(self.page_indexes):
            page_url = self.core.call_success(
                PageImg.page_get_img_url, self.doc_url, page_idx
            )

            promise = openpaperwork_core.promise.Promise(
                self.core, self.core.call_all,
                args=(
                    ProgressListener.on_progress, "print_load",
                    page_nb / len(self.page_indexes),
                    _("Loading {doc_id} p{page_idx} for printing").format(
                        doc_id=self.doc_id, page_idx=(page_idx + 1)
                    )
                )
            )
            promise = promise.then(lambda *args, **kwargs: None)
            promise = promise.then(openpaperwork_core.promise.DelayPromise(
                self.core, DELAY
            ))
            promise = promise.then(self.core.call_success(
                Url2Cairo.url_to_cairo_surface_promise, page_url
            ))
            promise = promise.then(self._add_surface)
            self.core.call_success(WorkQueue.work_queue_add_promise, "print", promise)

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=(
                ProgressListener.on_progress, "print_load", 1.0
            )
        )
        self.core.call_success(WorkQueue.work_queue_add_promise, "print", promise)

    def _add_surface(self, surface):
        LOGGER.info(
            "Got page rendering %d/%d",
            len(self.page_surfaces), len(self.page_indexes)
        )
        self.page_surfaces.append(surface)

    def get_nb_pages(self):
        return len(self.page_indexes)

    def get_nb_surfaces(self):
        return len(self.page_surfaces)

    def has_page_surface(self, page_nb):
        return page_nb < len(self.page_surfaces)

    def get_page_surface(self, page_nb):
        return self.page_surfaces[page_nb]

    def cancel(self):
        self.core.call_all(WorkQueue.work_queue_cancel_all, "print")
        self.page_surfaces = []


class PrintJob:
    def __init__(
            self, core, preloader, window, doc_id, nb_pages, active_page_nb,
            job_name, default_filename):
        self.core = core
        self.preloader = preloader
        self.window = window
        self.doc_id = doc_id
        self.nb_pages = nb_pages

        print_settings = Gtk.PrintSettings()
        self.print_op = Gtk.PrintOperation()
        self.print_op.set_print_settings(print_settings)
        self.print_op.set_n_pages(nb_pages)
        if active_page_nb >= 0:
            self.print_op.set_current_page(active_page_nb)
        self.print_op.set_use_full_page(True)
        self.print_op.set_job_name(job_name)
        self.print_op.set_export_filename(default_filename)
        self.print_op.set_allow_async(True)
        self.print_op.set_embed_page_setup(True)
        self.print_op.set_show_progress(True)
        self.print_op.connect("status-changed", self._status_changed)
        self.print_op.connect("paginate", self._paginate)
        self.print_op.connect("preview", self._preview)
        self.print_op.connect("ready", self._preview_ready)
        self.print_op.connect("got_page_size", self._preview_got_page_size)
        self.print_op.connect("begin-print", self._begin)
        self.print_op.connect("request-page-setup", self._request_page_setup)
        self.print_op.connect("draw-page", self._draw)
        self.print_op.connect("end-print", self._end)
        self.print_op.connect("done", self._done)

    def _status_changed(self, print_op):
        LOGGER.info(
            "Print status: %s: %s",
            print_op.get_status(), print_op.get_status_string()
        )

    def _preview(self, print_op, print_preview, print_context, win_parent):
        LOGGER.info("User requested a preview")

    def _preview_got_page_size(self, print_preview, print_context, page_setup):
        LOGGER.info("Preview: got page size")

    def _preview_ready(self, print_preview, print_context):
        LOGGER.info("Preview ready")

    def _paginate(self, print_operation, print_context):
        pagination = self.preloader.get_nb_surfaces()
        running = (pagination < self.nb_pages)
        return not running

    def _begin(self, print_op, print_context):
        LOGGER.info("Printing has begun")
        self.core.call_all(
            ProgressListener.on_progress, "print", 0.0, _("Printing %s") % self.doc_id
        )

    def _request_page_setup(
            self, print_op, print_context, page_nb, page_setup):
        LOGGER.info(
            "Computing page setup for %d/%d",
            page_nb, self.nb_pages
        )

        surface = self.preloader.get_page_surface(page_nb)
        img_width = surface.surface.get_width()
        img_height = surface.surface.get_height()

        # take care of rotating the page if required
        img_portrait = (img_width <= img_height)
        LOGGER.info(
            "Page %d/%d: Orientation portrait = %s",
            page_nb, self.nb_pages, img_portrait
        )
        page_setup.set_orientation(
            Gtk.PageOrientation.PORTRAIT
            if img_portrait else
            Gtk.PageOrientation.LANDSCAPE
        )

    def _draw(self, print_op, print_context, page_nb):
        LOGGER.info(
            "Printing of %s %d/%d ; DPI: %fx%f",
            self.doc_id, page_nb, self.nb_pages,
            print_context.get_dpi_x(),
            print_context.get_dpi_y()
        )
        self.core.call_all(
            ProgressListener.on_progress, "print", page_nb / self.nb_pages,
            _("Printing {doc_id} ({page_idx}/{nb_pages})").format(
                doc_id=self.doc_id, page_idx=page_nb, nb_pages=self.nb_pages
            )
        )

        surface = self.preloader.get_page_surface(page_nb)
        img_width = surface.surface.get_width()
        img_height = surface.surface.get_height()

        scaling = min(
            print_context.get_width() / img_width,
            print_context.get_height() / img_height,
        )

        cairo_ctx = print_context.get_cairo_context()
        cairo_ctx.scale(scaling, scaling)
        cairo_ctx.set_source_surface(surface.surface)
        cairo_ctx.paint()

    def _end(self, print_op, print_context):
        self.refs = []
        LOGGER.info("Printing has ended")
        self.core.call_all(ProgressListener.on_progress, "print", 1.0)

    def _done(self, print_op, print_op_result):
        LOGGER.info("Printing done")
        self.preloader.cancel()

    def run(self):
        self.print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self.window)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocOpener,
    DocPrint,
    GtkWindowListener,
    PageViewerListener,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=Docs,
                defaults=["paperwork_backend.model"],
            ),
            openpaperwork_core.Dependency(
                interface=PageImg,
                defaults=[
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ],
            ),
            openpaperwork_core.Dependency(
                interface=Url2Cairo,
                defaults=[
                    'paperwork_backend.cairo.pillow',
                    'paperwork_backend.cairo.poppler',
                ],
            ),
            openpaperwork_core.Dependency(
                interface=WorkQueue,
                defaults=['openpaperwork_core.work_queue.default'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        self.active_doc = None
        self.active_page_idx = None
        self.windows = []

        # WORKAROUND(Jflesch): keep a ref on the print operation to avoid
        # premature garbage collecting
        self._ref = None

        if not GTK_AVAILABLE:
            return

        self.core.call_success(WorkQueue.work_queue_create, "print")

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_close(self):
        pass

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def doc_print(self, doc_id, doc_url, page_indexes=None):
        active_page_idx = 0
        if self.active_doc[1] == doc_url:
            # prefer the current page when it makes sense
            active_page_idx = self.active_page_idx

        if page_indexes is None:
            nb_pages = self.core.call_success(
                Docs.doc_get_nb_pages_by_url, doc_url
            )
            if nb_pages is None:
                raise Exception("No page in the document, Nothing to print")
            page_indexes = list(range(0, nb_pages))
            job_name = "Paperwork " + doc_id
            default_filename = doc_id + ".pdf"
        else:
            job_name = "Paperwork {} p{}".format(
                doc_id, ",".join((str(p) for p in page_indexes))
            )
            default_filename = "{}_p{}".format(
                doc_id,
                "_p".join((str(p) for p in page_indexes))
            )

        try:
            active_page_nb = page_indexes.index(active_page_idx)
        except ValueError:
            active_page_nb = -1

        preloader = SurfacePreloader(self.core, doc_id, doc_url, page_indexes)
        print_job = PrintJob(
            self.core, preloader, self.windows[-1], doc_id, len(page_indexes),
            active_page_nb, job_name, default_filename
        )

        LOGGER.info(
            "Opening print dialog for document %s (pages: %s)",
            doc_url, page_indexes
        )
        preloader.start()
        print_job.run()

        self._ref = print_job

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
