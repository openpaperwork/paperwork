from typing import Dict
import abc


class AbstractDocViewerController(abc.ABC):
    @abc.abstractmethod
    def enter(self):
        ...

    @abc.abstractmethod
    def on_layout_size_allocate(self, layout):
        ...

    @abc.abstractmethod
    def on_page_size_obtained(self, page):
        ...

    @abc.abstractmethod
    def on_page_activated(self, page):
        ...

    @abc.abstractmethod
    def on_vscroll(self, vadj):
        ...

    @abc.abstractmethod
    def on_vscroll_changed(self, vadj):
        ...

    @abc.abstractmethod
    def on_vscroll_value_changed(self, vadj):
        ...

    @abc.abstractmethod
    def doc_reload(self):
        ...

    @abc.abstractmethod
    def doc_goto_page(self, page_idx):
        ...

    @abc.abstractmethod
    def docview_set_layout(self, name):
        ...

    @abc.abstractmethod
    def docview_set_zoom(self, name):
        ...

    @abc.abstractmethod
    def on_drag_motion(self, drag_context, x, y, time):
        ...

    @abc.abstractmethod
    def on_drag_leave(self, drag_context, time):
        ...

    @abc.abstractmethod
    def drag_and_drop_get_destination(self, x, y):
        ...

    @abc.abstractmethod
    def on_draw(self, cairo_context):
        ...

    @abc.abstractmethod
    def on_overlay_draw(self, overlay_drawing_area, cairo_context):
        ...

    @abc.abstractmethod
    def on_close(self):
        ...


class DocViewerControllerFactory(abc.ABC):
    @abc.abstractmethod
    def gtk_docview_get_controllers(
        self, out_controllers: Dict[str, AbstractDocViewerController], doc_viewer_plugin
    ):
        ...


class DocViewerComponentFactory(abc.ABC):
    @abc.abstractmethod
    def doc_open_components(self, out_pages: list, doc_id, doc_url):
        ...


class PageViewerListener(abc.ABC):
    @abc.abstractmethod
    def on_page_shown(self, page_idx):
        ...

    @abc.abstractmethod
    def on_page_size_obtained(self, page):
        ...


class DocViewerListener(abc.ABC):
    @abc.abstractmethod
    def on_gtk_docview_init(self):
        ...

    @abc.abstractmethod
    def on_layout_change(self, layout):
        ...

    @abc.abstractmethod
    def on_docview_closed_page(self, page):
        ...

    @abc.abstractmethod
    def on_docview_zoom_updated(self, zoom):
        ...


class DocViewer(abc.ABC):
    @abc.abstractmethod
    def doc_goto_page(self, page_idx: int):
        ...

    @abc.abstractmethod
    def doc_reload(self, doc_id, doc_url):
        ...

    @abc.abstractmethod
    def doc_goto_previous_page(self):
        ...

    @abc.abstractmethod
    def doc_goto_next_page(self):
        ...

    @abc.abstractmethod
    def docview_set_layout(self, name):
        ...

    @abc.abstractmethod
    def docview_set_zoom(self, zoom):
        ...

    @abc.abstractmethod
    def docview_add_page_viewer(self, page, visible=True):
        ...

    @abc.abstractmethod
    def docview_hide_page_viewer(self, page):
        ...

    @abc.abstractmethod
    def docview_show_page_viewer(self, page):
        ...

    @abc.abstractmethod
    def docview_get_headerbar(self):
        ...

    @abc.abstractmethod
    def docview_get_body(self):
        ...

    @abc.abstractmethod
    def docview_get_scrollwindow(self):
        ...

    @abc.abstractmethod
    def docview_set_bottom_margin(self, margin):
        ...

    @abc.abstractmethod
    def docview_switch_controller(self, core, name, new_controller_ctor):
        ...


class PageInfo(abc.ABC):
    @abc.abstractmethod
    def page_info_add_left(self, widget):
        ...

    @abc.abstractmethod
    def page_info_add_right(self, widget):
        ...


class PageMenuListener(abc.ABC):
    @abc.abstractmethod
    def on_page_menu_ready(self):
        ...


class PageMenu(abc.ABC):
    @abc.abstractmethod
    def page_menu_open(self):
        ...

    @abc.abstractmethod
    def page_menu_append_item(self, item, submenu_name=None):
        ...

    @abc.abstractmethod
    def screenshot_snap_page_action_menu(self, out_file):
        ...


class DocViewProgress(abc.ABC):
    ...
