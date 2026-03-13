from typing import Set
import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.docs import DocOpener, Docs

from paperwork_gtk.interfaces.doc_viewer import (
    AbstractDocViewerController,
    DocViewer,
    DocViewerControllerFactory,
    DocViewerListener,
    PageViewerListener
)
from paperwork_gtk.interfaces.drag_n_drop import DragAndDropDestination
from paperwork_gtk.interfaces.main_window import MainWindow
from paperwork_gtk.interfaces.main_window import MainWindowListener
from paperwork_gtk.interfaces.zoom import Zoom


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocOpener,
    DocViewer,
    PageViewerListener,
    DragAndDropDestination,
    MainWindowListener,
):
    LAYOUTS = {
        # name: pages per line (columns)
        'paged': 1,
        'grid': 3,
    }
    MAX_PAGES = max(LAYOUTS.values())

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Docs,
                defaults=["paperwork_backend.model"],
            ),
            openpaperwork_core.Dependency(
                interface=DocViewerControllerFactory,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=DocViewerListener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=['openpaperwork_gtk.mainloop.glib'],
            ),
            openpaperwork_core.Dependency(
                interface=MainWindow,
                defaults=['paperwork_gtk.mainwindow.window'],
            ),
            openpaperwork_core.Dependency(
                interface=Zoom,
                defaults=[
                    'paperwork_gtk.gesture.zoom',
                    'paperwork_gtk.keyboard_shortcut.zoom',
                ],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.controllers = {}
        self.widget_tree = None
        self.scroll = None
        self.page_layout = None
        self.pages = []
        self.nb_visible_pages = 0
        self.widget_to_page = {}
        self.page_to_widget = {}
        self.nb_columns = self.MAX_PAGES

        self.zoom = 0.0
        self.layout_name = None
        self.requested_page_idx = 0

        self.active_page_idx = 0
        self.active_doc = (None, None)
        self.active_doc_mtime = None

        self.core.call_success(
            GtkResources.gtk_load_css,
            "paperwork_gtk.mainwindow.docview", "docview.css"
        )

        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docview", "docview.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.scroll = self.widget_tree.get_object("docview_scroll")
        self.scroll.get_vadjustment().connect(
            "value-changed", self._on_vscroll_value_changed
        )
        self.scroll.get_vadjustment().connect(
            "changed", self._on_vscroll_changed
        )

        self.overlay = self.widget_tree.get_object("docview_drawingarea")
        self.overlay.connect("draw", self._on_overlay_draw)

        self.page_layout = self.widget_tree.get_object("docview_page_layout")
        self.page_layout.connect(
            "size-allocate", self._on_layout_size_allocate
        )
        self.page_layout.connect("child-activated", self._on_child_activated)

        self.page_layout.connect("drag-motion", self._on_drag_motion)
        self.page_layout.connect("drag-leave", self._on_drag_leave)
        self.page_layout.connect("draw", self._on_draw)

        self.core.call_all(
            GtkResources.gtk_fix_headerbar_buttons,
            self.widget_tree.get_object("docview_header")
        )

        self.on_mainwindow_fold_change()

        self.widget_tree.get_object("docview_back").connect(
            "clicked",
            lambda *args, **kwargs: (
                self.core.call_all(MainWindow.mainwindow_show, "left")
            )
        )

        self.core.call_all(
            MainWindow.mainwindow_add, side="right", name="docview", prio=10000,
            header=self.widget_tree.get_object("docview_header"),
            body=self.widget_tree.get_object("docview_body"),
        )

        self.core.call_success(
            Mainloop.mainloop_schedule, self.core.call_all,
            DocViewerListener.on_gtk_docview_init, self
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def _on_child_activated(self, page_layout, child):
        page = self.widget_to_page[child]
        for controller in self.controllers.values():
            controller.on_page_activated(page)

    def docview_set_bottom_margin(self, height):
        self.widget_tree.get_object("docview_padding").set_size_request(
            1, height + 10
        )

    def docview_get_headerbar(self):
        return self.widget_tree.get_object("docview_header")

    def docview_get_body(self):
        return self.widget_tree.get_object("docview_overlay")

    def docview_get_scrollwindow(self):
        return self.widget_tree.get_object("docview_scroll")

    def docview_switch_controller(self, core, name, new_controller_ctor):
        self.controllers[name].exit()
        new_controller = new_controller_ctor(core, self)
        LOGGER.info(
            "%s: %s --> %s",
            name, str(self.controllers[name]), str(new_controller)
        )
        self.controllers[name] = new_controller
        new_controller.enter()

    def _on_layout_size_allocate(self, layout, allocation):
        for controller in self.controllers.values():
            controller.on_layout_size_allocate(layout)

    def _on_vscroll_value_changed(self, vadj):
        for controller in self.controllers.values():
            controller.on_vscroll_value_changed(vadj)

    def _on_vscroll_changed(self, vadj):
        for controller in self.controllers.values():
            controller.on_vscroll_changed(vadj)

    def _on_drag_motion(self, layout, drag_context, x, y, time):
        for controller in self.controllers.values():
            controller.on_drag_motion(drag_context, x, y, time)

    def _on_drag_leave(self, layout, drag_context, time):
        for controller in self.controllers.values():
            controller.on_drag_leave(drag_context, time)

    def drag_and_drop_get_destination(self, widget, x, y):
        if widget != self.page_layout:
            return None
        for controller in self.controllers.values():
            r = controller.drag_and_drop_get_destination(x, y)
            if r is not None:
                return r
        return None

    def _on_draw(self, layout, cairo_context):
        for controller in self.controllers.values():
            controller.on_draw(cairo_context)

    def _on_overlay_draw(self, widget, cairo_context):
        for controller in self.controllers.values():
            controller.on_overlay_draw(widget, cairo_context)

    def doc_close(self):
        for page in self.pages:
            page.set_visible(False)
        for controller in self.controllers.values():
            controller.on_close()

    def _build_flow_box_child(self, child):
        widget = Gtk.FlowBoxChild.new()
        widget.set_visible(True)
        widget.set_property('name', 'docview_page')
        widget.set_property('halign', Gtk.Align.CENTER)
        widget.add(child)
        return widget

    def doc_open(self, doc_id, doc_url):
        self.doc_close()

        self.core.call_success(
            MainWindow.mainwindow_show, side="right", name="docview"
        )

        self.zoom = 0.0
        self.layout_name = 'grid'
        self.active_doc = (doc_id, doc_url)
        self.active_doc_mtime = self.core.call_success(
            Docs.doc_get_mtime_by_url, doc_url
        )
        self.active_page_idx = 0

        self.pages = []
        self.widget_to_page = {}
        self.page_to_widget = {}
        self.nb_visible_pages = 0

        self.controllers: Set[AbstractDocViewerController] = {}
        self.core.call_all(
            DocViewerControllerFactory.gtk_docview_get_controllers, self.controllers, self
        )
        for controller in self.controllers.values():
            controller.enter()

    def doc_reload(self, doc_id, doc_url):
        if self.active_doc != (doc_id, doc_url):
            LOGGER.info(
                "Reload requested for document %s, but active doc is %s",
                (doc_id, doc_url), self.active_doc
            )
            return
        mtime = self.core.call_success(Docs.doc_get_mtime_by_url, doc_url)
        if mtime == self.active_doc_mtime:
            LOGGER.info(
                "Reload for document %s requested, but mtime hasn't changed"
                " (%s)", doc_url, mtime
            )
            return
        self.active_doc_mtime = mtime
        LOGGER.info("Reloading document %s", self.active_doc)
        for controller in self.controllers.values():
            controller.doc_reload()

    def on_page_size_obtained(self, page):
        # page may been wrapped
        page = self.pages[page.page_idx]
        for controller in self.controllers.values():
            controller.on_page_size_obtained(page)

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

        page = self.pages[page_idx]
        widget = self.page_to_widget[page]
        self.page_layout.select_child(widget)

    def doc_goto_previous_page(self):
        self.doc_goto_page(self.active_page_idx - 1)

    def doc_goto_next_page(self):
        self.doc_goto_page(self.active_page_idx + 1)

    def doc_goto_page(self, page_idx):
        LOGGER.info(
            "Going to page %d (nb pages=%d)",
            page_idx, self.nb_visible_pages
        )
        if page_idx < 0:
            page_idx = 0
        if page_idx >= self.nb_visible_pages:
            page_idx = self.nb_visible_pages - 1
        self.requested_page_idx = page_idx
        for controller in self.controllers.values():
            controller.doc_goto_page(page_idx)
        self.core.call_all(PageViewerListener.on_page_shown, page_idx)

    def docview_set_layout(self, name):
        self.layout_name = name
        for controller in self.controllers.values():
            controller.docview_set_layout(name)

    def docview_set_zoom(self, zoom):
        self.zoom = zoom
        for controller in self.controllers.values():
            controller.docview_set_zoom(zoom)
        self.core.call_all(DocViewerListener.on_docview_zoom_updated, zoom)

    def docview_add_page_viewer(self, page, visible=True):
        widget = self._build_flow_box_child(page.widget)
        self.widget_to_page[widget] = page
        self.page_to_widget[page] = widget
        self.pages.append(page)
        if visible:
            self.nb_visible_pages += 1
            self.page_layout.add(widget)

    def docview_hide_page_viewer(self, page):
        # Jflesch> Hiding is not enough. We have to remove the widget
        # otherwise it's still taken into account when computing
        # the layout (keep in mind that homogenous is set to True)
        self.page_layout.remove(self.page_to_widget[page])
        self.nb_visible_pages -= 1

    def docview_show_page_viewer(self, page):
        # XXX(Jflesch): We mess up the order of the widgets here. But since
        # only the scan viewer uses this method at the moment, it's fine.
        self.page_layout.add(self.page_to_widget[page])
        self.nb_visible_pages += 1

    def on_mainwindow_fold_change(self):
        folded = self.core.call_success(MainWindow.mainwindow_get_folded)
        self.widget_tree.get_object("docview_header").set_show_close_button(
            not folded
        )
        self.widget_tree.get_object("docview_back").set_visible(folded)
