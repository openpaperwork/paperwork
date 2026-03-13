import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False
    Gtk = None  # make static analysis happy

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.activity import ActivityListener
from openpaperwork_gtk.interfaces.gtk import GtkResources
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.i18n_scanner import I18nScanner
from paperwork_backend.interfaces.scan import Scan, ScanListener
from paperwork_backend.interfaces.scan2doc import Scan2Doc, Scan2DocListener

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_viewer import DocViewer
from paperwork_gtk.interfaces.new_doc import NewDoc
from paperwork_gtk.interfaces.page_add import PageAddButtons
from paperwork_gtk.interfaces.page_add import PageAddButtonsSources
from paperwork_gtk.interfaces.page_add import PageAddButtonsSourcesPopover


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    PageAddButtonsSources,
    ScanListener,
    Scan2DocListener,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=ActivityListener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=Config,
                defaults=['openpaperwork_core.config'],
            ),
            openpaperwork_core.Dependency(
                interface=DocViewer,
                defaults=["paperwork_gtk.mainwindow.docview"],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=PageAddButtons,
                defaults=["paperwork_gtk.mainwindow.docview.pageadd.buttons"],
            ),
            openpaperwork_core.Dependency(
                interface=PageAddButtonsSourcesPopover,
                defaults=[
                    'paperwork_gtk.mainwindow.docview.pageadd.source_popover'
                ],
            ),
            openpaperwork_core.Dependency(
                interface=I18nScanner,
                defaults=['paperwork_backend.i18n.scanner'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=["openpaperwork_gtk.mainloop.glib"],
            ),
            openpaperwork_core.Dependency(
                interface=Scan,
                defaults=['paperwork_backend.docscan.scan2doc'],
            ),
            openpaperwork_core.Dependency(
                interface=Scan2Doc,
                defaults=['paperwork_backend.docscan.libinsane'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        self.busy = False
        opt = self.core.call_success(
            Config.config_build_simple, "pageadd", "scanner_sources", lambda: []
        )
        self.core.call_all(Config.config_register, "pageadd_sources", opt)

        self.core.call_all(
            Config.config_add_observer, "scanner_dev_id", self._update_sources
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def _update_sources(self):
        def get_sources(dev=None):
            if dev is None:
                source_names = []
            else:
                sources = dev.dev.get_children()
                source_names = []
                for src in sources:
                    source_names.append(src.get_name())
                sources = None
            LOGGER.info("Scanner sources: %s", source_names)
            return source_names

        def store_sources(sources):
            self.core.call_all(Config.config_put, "pageadd_sources", list(sources))

        promise = self.core.call_success(Scan.scan_get_scanner_promise)
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, get_sources
        ))
        promise = promise.then(store_sources)
        promise = promise.then(
            self.core.call_all, PageAddButtonsSourcesPopover.pageadd_sources_refresh
        )
        self.core.call_success(Scan.scan_schedule, promise)

    def pageadd_get_sources(self, out: list):
        sources = self.core.call_success(Config.config_get, "pageadd_sources")
        for source in list(sources):
            widget_tree = self.core.call_success(
                GtkResources.gtk_load_widget_tree,
                "paperwork_gtk.mainwindow.docview.pageadd", "source_box.glade"
            )
            source_txt = self.core.call_success(
                I18nScanner.i18n_scanner_source, source
            )
            source_txt = _("Scan from %s") % source_txt

            img = "view-paged-symbolic"
            if "flatbed" in source:
                img = "document-new-symbolic"

            widget_tree.get_object("source_image").set_from_icon_name(
                img, Gtk.IconSize.SMALL_TOOLBAR
            )
            widget_tree.get_object("source_name").set_text(source_txt)

            out.append(
                (
                    widget_tree.get_object("source_selector"),
                    source_txt, source, self._on_scan
                )
            )

    def _on_scan(self, doc_id, doc_url, source_id):
        LOGGER.info("Scanning from %s", source_id)

        if doc_id is None or doc_url is None:
            (doc_id, doc_url) = self.core.call_success(NewDoc.get_new_doc)
            self.core.call_all(DocOpener.doc_open, doc_id, doc_url)

        self.core.call_all(ActivityListener.on_busy)
        self.core.call_all(PageAddButtons.pageadd_busy_add)
        self.busy = True

        promise = self.core.call_success(
            Scan2Doc.scan2doc_promise, doc_id=doc_id, doc_url=doc_url,
            source_id=source_id
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_all, PageAddButtons.pageadd_busy_remove,
        )
        self.core.call_success(Scan.scan_schedule, promise)

    @openpaperwork_core.noop
    def on_scan2doc_start(self, scan_id, doc_id, doc_url):
        pass

    @openpaperwork_core.noop
    def on_scan2doc_end(self, scan_id, doc_id, doc_url):
        pass

    def on_scan2doc_page_scanned(self, scan_id, doc_id, doc_url, nb_pages):
        LOGGER.info(
            "Page scanned: %s p%d (scan id = %d)", doc_id, nb_pages, scan_id
        )
        self.core.call_all(DocViewer.doc_reload, doc_id, doc_url)

    def on_scan_started(self, scan_id):
        if not self.busy:
            return
        self.core.call_all(ActivityListener.on_idle)
        self.busy = False

    @openpaperwork_core.noop
    def on_scan_feed_start(self, scan_id):
        pass

    @openpaperwork_core.noop
    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        pass

    @openpaperwork_core.noop
    def on_scan_chunk(self, scan_id, scan_params, img_chunk):
        pass

    @openpaperwork_core.noop
    def on_scan_page_end(self, scan_id, page_nb, img):
        pass

    @openpaperwork_core.noop
    def on_scan_feed_end(self, scan_id):
        pass
