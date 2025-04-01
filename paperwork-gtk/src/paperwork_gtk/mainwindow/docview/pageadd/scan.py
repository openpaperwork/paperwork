import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps

from .... import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'gtk_scan_buttons_popover_sources',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_scan_buttons_popover',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageadd.source_popover'
                ],
            },
            {
                'interface': 'i18n_scanner',
                'defaults': ['paperwork_backend.i18n.scanner'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
            {
                'interface': 'scan2doc',
                'defaults': ['paperwork_backend.docscan.scan2doc'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.busy = False
        opt = self.core.call_success(
            "config_build_simple", "pageadd", "scanner_sources", lambda: []
        )
        self.core.call_all("config_register", "pageadd_sources", opt)

        self.core.call_all(
            "config_add_observer", "scanner_dev_id", self._update_sources
        )

        self.core.call_all(
            "mainloop_schedule", self.core.call_all,
            "pageadd_sources_refresh"
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
            self.core.call_all("config_put", "pageadd_sources", list(sources))

        promise = self.core.call_success("scan_get_scanner_promise")
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, get_sources
        ))
        promise = promise.then(store_sources)
        promise = promise.then(self.core.call_all, "pageadd_sources_refresh")
        self.core.call_success("scan_schedule", promise)

    def pageadd_get_sources(self, out: list):
        sources = self.core.call_success("config_get", "pageadd_sources")
        for source in list(sources):
            widget_tree = self.core.call_success(
                "gtk_load_widget_tree",
                "paperwork_gtk.mainwindow.docview.pageadd", "source_box.glade"
            )
            source_txt = self.core.call_success(
                "i18n_scanner_source", source
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
            (doc_id, doc_url) = self.core.call_success("get_new_doc")
            self.core.call_all("doc_open", doc_id, doc_url)

        self.core.call_all("on_busy")
        self.core.call_all("pageadd_busy_add")
        self.busy = True

        promise = self.core.call_success(
            "scan2doc_promise", doc_id=doc_id, doc_url=doc_url,
            source_id=source_id
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_all, "pageadd_busy_remove"
        )
        self.core.call_success("scan_schedule", promise)

    def on_scan2doc_page_scanned(self, scan_id, doc_id, doc_url, nb_pages):
        LOGGER.info(
            "Page scanned: %s p%d (scan id = %d)", doc_id, nb_pages, scan_id
        )
        self.core.call_all("doc_reload", doc_id, doc_url)

    def on_scan_started(self, scan_id):
        if not self.busy:
            return
        self.core.call_all("on_idle")
        self.busy = False
