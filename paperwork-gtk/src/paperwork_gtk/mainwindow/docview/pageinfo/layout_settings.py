import logging

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources
from paperwork_gtk.interfaces.page_drawer import PageDrawer
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotProvider
import openpaperwork_gtk.deps

from paperwork_gtk.interfaces.doc_layout import DocLayout
from paperwork_gtk.interfaces.doc_viewer import DocViewer
from paperwork_gtk.interfaces.doc_viewer import DocViewerListener
from paperwork_gtk.interfaces.doc_viewer import PageInfo
from paperwork_gtk.interfaces.page_boxes import PageViewBoxesAll
from paperwork_gtk.interfaces.zoom import Zoom


try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocLayout,
    DocViewerListener,
    ScreenshotProvider,
):
    LAYOUTS = {
        'paged': {
            'icon': 'view-paged-symbolic',
        },
        'grid': {
            'icon': 'view-grid-symbolic',
        },
    }

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": DocViewer,
                "defaults": ["paperwork_gtk.mainwindow.docview"],
            },
            {
                "interface": Fs,
                "defaults": ["openpaperwork_gtk.fs.gio"],
            },
            {
                'interface': PageDrawer,
                'defaults': ['paperwork_gtk.mainwindow.docview.pageview'],
            },
            {
                'interface': PageInfo,
                'defaults': ['paperwork_gtk.mainwindow.docview.pageinfo'],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                "interface": PageViewBoxesAll,
                "defaults": [],
            },
            {
                'interface': Screenshot,
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
            {
                "interface": Zoom,
                "defaults": ["paperwork_gtk.gesture.zoom"],
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.widget_tree = None
        self.layout_icon = None
        self.layout_button = None
        self.notify = True

        self.core.call_success(
            GtkResources.gtk_load_css,
            "paperwork_gtk.mainwindow.docview.pageinfo", "layout_settings.css"
        )

        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docview.pageinfo",
            "layout_settings.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.layout_icon = self.widget_tree.get_object("page_layout_icon")
        self.layout_button = self.widget_tree.get_object("page_layout")
        self.layout_button.connect("clicked", self.gtk_open_layout_settings)

        self.zoom = self.widget_tree.get_object("adjustment_zoom")
        self.zoom.connect("value-changed", self._on_zoom_changed)

        self.all_boxes = self.widget_tree.get_object("show_all_boxes")
        self.all_boxes.connect("notify::active", self._notify_all_boxes)

        self.layout_buttons = {
            self.widget_tree.get_object("layout_grid"): {
                "handler": None,
                "layout": "grid",
            },
            self.widget_tree.get_object("layout_paged"): {
                "handler": None,
                "layout": "paged",
            },
        }
        for button in self.layout_buttons.keys():
            self.layout_buttons[button]['handler'] = button.connect(
                "clicked", self._on_layout_change
            )

        self.core.call_success(PageInfo.page_info_add_left, self.layout_button)

        scroll = self.core.call_success(DocViewer.docview_get_scrollwindow)
        self.core.call_all(Zoom.on_zoomable_widget_new, scroll, self.zoom)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_layout_change(self, layout_name):
        if self.layout_icon is None:
            return

        icon = self.LAYOUTS[layout_name]['icon']
        # smallest icon size available
        self.layout_icon.set_from_icon_name(icon, Gtk.IconSize.SMALL_TOOLBAR)

    def _on_layout_change(self, widget):
        assert widget in self.layout_buttons
        layout = self.layout_buttons[widget]['layout']
        self.core.call_all(DocViewer.docview_set_layout, layout)

    def gtk_open_layout_settings(self, *args, **kwargs):
        menu = self.widget_tree.get_object("layout_settings")
        menu.set_relative_to(self.layout_button)
        menu.set_visible(True)

    def gtk_close_layout_settings(self, *args, **kwargs):
        menu = self.widget_tree.get_object("layout_settings")
        menu.set_visible(False)

    def _on_zoom_changed(self, _=None):
        new_value = self.zoom.get_value()
        if self.notify:
            self.core.call_all(DocViewer.docview_set_zoom, new_value)

    def _notify_all_boxes(self, *args, **kwargs):
        active = self.all_boxes.get_active()
        self.core.call_all(PageViewBoxesAll.set_all_boxes_visible, active)
        self.core.call_all(PageDrawer.pageview_refresh_all)

    def on_docview_zoom_updated(self, zoom):
        current = self.zoom.get_value()
        if current != zoom:
            self.notify = False
            try:
                self.zoom.set_value(zoom)
            finally:
                self.notify = True

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return

        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("layout_settings"),
            self.core.call_success(Fs.fs_join, out_dir, "docview_layout.png"),
        )
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("layout_paged"),
            self.core.call_success(
                Fs.fs_join, out_dir, "docview_layout_paged.png"
            ),
            margins=(50, 50, 50, 50)
        )
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("layout_grid"),
            self.core.call_success(
                Fs.fs_join, out_dir, "docview_layout_grid.png"
            ),
            margins=(50, 50, 50, 50)
        )
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("scale_zoom"),
            self.core.call_success(
                Fs.fs_join, out_dir, "docview_layout_scale.png"
            ),
            margins=(50, 50, 50, 50)
        )
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("show_all_boxes"),
            self.core.call_success(
                Fs.fs_join, out_dir, "docview_layout_show_all_boxes.png"
            ),
            margins=(275, 50, 50, 50)
        )

    @openpaperwork_core.noop
    def on_docview_closed_page(self, page):
        pass

    @openpaperwork_core.noop
    def on_gtk_docview_init(self):
        pass
