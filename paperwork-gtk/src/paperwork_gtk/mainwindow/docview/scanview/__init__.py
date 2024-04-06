import logging

import openpaperwork_core
import openpaperwork_core.deps

try:
    from gi.repository import GObject
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

    # workaround so chkdeps can still be called
    class GObject(object):  # type: ignore[no-redef]
        TYPE_BOOLEAN = 0

        class SignalFlags(object):
            RUN_LAST = 0

        class GObject(object):
            pass


LOGGER = logging.getLogger(__name__)


class Scan(GObject.GObject):
    """
    Implements the same interface than the mainwindow.docview.pageview.Page
    objects, but display any scan relative to the current document.
    """

    __gsignals__ = {
        # never emitted
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),

        # emitted immediately and when a scan is started
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),

        # never emitted
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),

        'visibility_changed': (GObject.SignalFlags.RUN_LAST, None, (
            # TODO(Jflesch): not implemented here (never emitted), but not
            # used anywhere anyway.
            GObject.TYPE_BOOLEAN,
        )),
    }

    def __init__(self, core, plugin, doc_id, page_idx, scan_id=None):
        super().__init__()
        self.core = core
        self.plugin = plugin
        self.doc_id = doc_id
        self.zoom = 1.0
        self.page_idx = page_idx

        self.scan_id = scan_id

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.scanview", "scanview.glade"
        )
        self.widget = self.widget_tree.get_object("scanview_area")
        self.visible = False

    def __str__(self):
        return "Scan renderer ({})".format(self.doc_id)

    def set_visible(self, visible):
        if visible == self.visible:
            return
        LOGGER.info("Scan renderer: Visible: {}".format(visible))
        self.visible = visible

    def start(self):
        LOGGER.info("Scan renderer: start")
        size = self.get_size()
        self.widget.set_size_request(size[0], size[1])
        self.widget.queue_resize()
        self.core.call_all("draw_scan_start", self.widget, self.scan_id)
        self.widget.set_visible(True)

    def stop(self):
        LOGGER.info("Scan renderer: stop")
        self.core.call_all("draw_scan_stop", self.widget)
        self.widget.set_visible(False)

    def get_visible(self):
        return self.visible

    def load(self):
        # the docview rely on this signal to know when pagss have been loaded
        # (in other words, when their size have been defined).
        # It remains in state 'loading' as long as not all the pages have
        # reported having be loaded --> we report immediately ourselves
        # as loaded
        self.core.call_all("on_page_size_obtained", self)
        self.emit("size_obtained")

    def close(self):
        pass

    def get_zoom(self):
        return self.zoom

    def set_zoom(self, zoom):
        self.zoom = zoom
        self.resize()

    def get_full_size(self):
        if self.scan_id is None:
            return (0, 0)
        size = self.core.call_success("draw_scan_get_scan_size", self.scan_id)
        if size is None:
            LOGGER.warning("Unknown scan_id: %s !?", self.scan_id)
            return (0, 0)
        return size

    def get_size(self):
        size = self.get_full_size()
        LOGGER.info("Scan size: %dx%d", size[0], size[1])
        return (
            int(size[0] * self.zoom),
            int(size[1] * self.zoom)
        )

    def resize(self):
        if self.scan_id is None:
            return
        size = self.get_size()
        self.widget.set_size_request(size[0], size[1])
        self.core.call_all("on_page_size_obtained", self)
        self.emit("size_obtained")
        self.widget.queue_resize()

    def refresh(self, reload=False):
        self.widget.queue_draw()

    def hide(self):
        pass

    def show(self):
        pass


if GLIB_AVAILABLE:
    GObject.type_register(Scan)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -10000

    def __init__(self):
        super().__init__()
        self.scan = None
        self.doc_id = None
        self.doc_url = None

    def get_interfaces(self):
        return [
            'gtk_pageview',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_drawer_scan',
                'defaults': [
                    'openpaperwork_gtk.drawer.scan',
                    'paperwork_gtk.drawer.calibration',
                ],
            },
        ]

    def doc_open_components(self, out: list, doc_id, doc_url):
        self.doc_id = doc_id
        self.doc_url = doc_url

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            nb_pages = 0
        scan_id = self.core.call_success("scan2doc_doc_id_to_scan_id", doc_id)
        self.scan = Scan(self.core, self, doc_id, nb_pages, scan_id)
        if scan_id is None:
            out.append((False, self.scan))  # invisible
        else:
            out.append((True, self.scan))  # visible
            self.scan.start()

    def on_scan2doc_start(self, scan_id, doc_id, doc_url):
        if self.scan is None:
            return
        if doc_id != self.doc_id:
            return
        self.scan.scan_id = scan_id

    def on_scan_feed_start(self, scan_id):
        if self.scan is None:
            return
        if scan_id != self.scan.scan_id:
            return
        self.scan.start()
        self.core.call_all("docview_show_page_viewer", self.scan)

    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        if self.scan is None:
            return
        if scan_id != self.scan.scan_id:
            return

        self.scan.resize()

        nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", self.doc_url
        )
        if nb_pages is None:
            nb_pages = 0

        handle_id = None

        def goto_page(*args, **kwargs):
            self.scan.widget.disconnect(handle_id)
            self.core.call_all("doc_goto_page", nb_pages)

        self.core.call_all("doc_goto_page", nb_pages)
        handle_id = self.scan.widget.connect("size-allocate", goto_page)

    def on_scan_chunk(self, scan_id, *args, **kwargs):
        self.scan.resize()

    def on_scan2doc_page_scanned(self, scan_id, doc_id, doc_url, page_idx):
        if self.scan is None:
            return
        if scan_id != self.scan.scan_id:
            return

        nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", self.doc_url
        )
        assert nb_pages is not None

        LOGGER.info("Displaying new page %d", nb_pages - 1)
        self.core.call_all("doc_goto_page", nb_pages - 1)

    def on_scan_feed_end(self, scan_id):
        if self.scan is None:
            return
        if scan_id != self.scan.scan_id:
            return
        self.core.call_all("docview_hide_page_viewer", self.scan)
        self.scan.stop()

    def on_scan2doc_end(self, scan_id, doc_id, doc_url):
        if self.scan is None:
            return
        if doc_id != self.doc_id:
            return
        self.scan.scan_id = None
