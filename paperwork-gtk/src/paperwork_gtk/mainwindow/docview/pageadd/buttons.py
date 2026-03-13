import logging

from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotProvider
from openpaperwork_gtk.interfaces.widgets import WidgetActivity

from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.scan import ScanListener

from paperwork_gtk.interfaces.doc_viewer import DocViewer
from paperwork_gtk.interfaces.new_doc import NewDoc
from paperwork_gtk.interfaces.page_add import PageAddButtons


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    DocOpener,
    PageAddButtons,
    ScanListener,
    ScreenshotProvider,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=DocViewer,
                defaults=['paperwork_gtk.mainwindow.docview'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_gtk.fs.gio'],
            ),
            openpaperwork_core.Dependency(
                interface=NewDoc,
                defaults=['paperwork_gtk.new_doc'],
            ),
            openpaperwork_core.Dependency(
                interface=Screenshot,
                defaults=['openpaperwork_gtk.screenshots'],
            ),
            openpaperwork_core.Dependency(
                interface=WidgetActivity,
                defaults=["openpaperwork_gtk.busy.mouse"],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.default_action = None
        self.default_action_args = None
        self.active_doc_id = None
        self.active_doc_url = None
        self.busy = 0

        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docview.pageadd", "buttons.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.widget_tree.get_object("pageadd_button").connect(
            "clicked", self._on_clicked
        )

        headerbar = self.core.call_success(DocViewer.docview_get_headerbar)
        headerbar.pack_start(self.widget_tree.get_object("pageadd_buttons"))

    def pageadd_buttons_set_source_popover(self, selector):
        self.widget_tree.get_object("pageadd_switch").set_popover(selector)

    def _update_sensitivity(self):
        sensitive = (
            self.default_action is not None and self.busy <= 0
        )
        button = self.widget_tree.get_object("pageadd_button")
        button.set_sensitive(sensitive)
        self.core.call_all(WidgetActivity.on_widget_busyness_changed, button, sensitive)

    def pageadd_set_default_action(self, txt, callback, *args):
        self.default_action = callback
        self.default_action_args = args
        self.widget_tree.get_object("pageadd_button").set_label(txt)
        self._update_sensitivity()

    def pageadd_busy_add(self):
        self.busy += 1
        self._update_sensitivity()

    def pageadd_busy_remove(self):
        self.busy -= 1
        self._update_sensitivity()

    def _on_clicked(self, widget):
        self.default_action(
            self.active_doc_id, self.active_doc_url,
            *self.default_action_args
        )

    def doc_open(self, doc_id, doc_url):
        self.active_doc_id = doc_id
        self.active_doc_url = doc_url
        self._update_sensitivity()

    def doc_close(self):
        self.active_doc_id = None
        self.active_doc_url = None
        self._update_sensitivity()

    def on_scan_feed_start(self, scan_id):
        self.pageadd_busy_add()

    def on_scan_feed_end(self, scan_id):
        self.pageadd_busy_remove()

    def screenshot_snap_all_doc_widgets(self, out_dir):
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("pageadd_buttons"),
            self.core.call_success(Fs.fs_join, out_dir, "page_add.png")
        )

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    @openpaperwork_core.noop
    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        pass

    @openpaperwork_core.noop
    def on_scan_started(self, scan_id):
        pass

    @openpaperwork_core.noop
    def on_scan_chunk(self, scan_id, scan_params, img_chunk):
        pass

    @openpaperwork_core.noop
    def on_scan_page_end(self, scan_id, page_nb, img):
        pass
