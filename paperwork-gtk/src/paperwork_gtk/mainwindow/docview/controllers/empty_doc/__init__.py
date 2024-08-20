import logging

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    CAIRO_AVAILABLE = False

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

try:
    import gi
    gi.require_version('Pango', '1.0')
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import Pango
    from gi.repository import PangoCairo
    PANGO_AVAILABLE = True
except (ImportError, ValueError):
    PANGO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_gtk.deps

from .. import BaseDocViewController
from ..... import _


LOGGER = logging.getLogger(__name__)


class BaseDisplayNewDocController(BaseDocViewController):
    def __init__(self, docview, empty_doc_plugin):
        super().__init__(docview)
        self.empty_doc_plugin = empty_doc_plugin
        self.core = empty_doc_plugin.core

    def _switch_controller(self):
        nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", self.plugin.active_doc[1]
        )
        if nb_pages is None:
            nb_pages = 0

        if nb_pages > 0 or self.empty_doc_plugin.scanning:
            self.plugin.docview_switch_controller(
                "new_doc",
                lambda docview: NoDisplayController(
                    docview, self.empty_doc_plugin
                )
            )
        else:
            self.plugin.docview_switch_controller(
                "new_doc",
                lambda docview: DisplayNewDocController(
                    docview, self.empty_doc_plugin
                )
            )

    def doc_reload(self):
        self._switch_controller()


class DisplayNewDocController(BaseDisplayNewDocController):
    def __init__(self, docview, plugin):
        super().__init__(docview, plugin)
        self.core = docview.core

    def enter(self):
        self.plugin.overlay.set_visible(True)

    def on_overlay_draw(self, overlay_drawing_area, cairo_ctx):
        if self.empty_doc_plugin.scanning:
            self._switch_controller()
            return

        img = self.empty_doc_plugin.img
        alloc = overlay_drawing_area.get_allocation()
        style = overlay_drawing_area.get_style_context()
        color = style.get_color(Gtk.StateFlags.ACTIVE)

        layout = PangoCairo.create_layout(cairo_ctx)
        layout.set_text(_("Empty"), -1)  # text must be short
        txt_size = layout.get_size()
        if 0 in txt_size:
            return

        zoom = img.get_height() / txt_size[1]
        scaled_txt_width = txt_size[0] * zoom

        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(color.red, color.green, color.blue, 0.33)
            cairo_ctx.mask_surface(
                self.empty_doc_plugin.img,
                ((alloc.width - img.get_width() - scaled_txt_width) / 2),
                ((alloc.height - img.get_height()) / 2),
            )
            cairo_ctx.fill()
        finally:
            cairo_ctx.restore()

        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(color.red, color.green, color.blue, 0.33)
            cairo_ctx.translate(
                ((alloc.width - img.get_width() - scaled_txt_width) / 2) +
                img.get_width(),
                ((alloc.height - img.get_height()) / 2),
            )
            cairo_ctx.scale(zoom * Pango.SCALE, zoom * Pango.SCALE)
            PangoCairo.update_layout(cairo_ctx, layout)
            PangoCairo.show_layout(cairo_ctx, layout)
        finally:
            cairo_ctx.restore()


class NoDisplayController(BaseDisplayNewDocController):
    def enter(self):
        self.plugin.overlay.set_visible(False)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.scanning = False

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_docview_controller',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def init(self, core):
        super().init(core)

        if not CAIRO_AVAILABLE:
            # chkdeps() must still be callable
            return

        file_path_ctx = self.core.call_success(
            "resources_get_file",
            "paperwork_gtk.mainwindow.docview.controllers.empty_doc",
            "empty_doc.png"
        )
        with file_path_ctx as file_path:
            self.img = cairo.ImageSurface.create_from_png(file_path)

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)
        if not PANGO_AVAILABLE:
            out['pango'].update(openpaperwork_core.deps.PANGO)

    def on_scan2doc_start(self, *args, **kwargs):
        self.scanning = True

    def on_scan2doc_end(self, *args, **kwargs):
        self.scanning = False

    def gtk_docview_get_controllers(self, out: dict, docview):
        nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", docview.active_doc[1]
        )
        if nb_pages is None:
            nb_pages = 0

        out['new_doc'] = (
            DisplayNewDocController(docview, self)
            if nb_pages <= 0 else
            NoDisplayController(docview, self)
        )
