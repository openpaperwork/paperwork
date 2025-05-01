import math

try:
    import gi
    gi.require_foreign("cairo")
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    CAIRO_AVAILABLE = False

try:
    from gi.repository import GObject
    GI_AVAILABLE = True
except (ImportError, ValueError):
    GI_AVAILABLE = False

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    # workaround so chkdeps can still be called
    class Gtk(object):
        class DrawingArea(object):
            pass
    GTK_AVAILABLE = False


from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

import openpaperwork_gtk.deps

from paperwork_backend.interfaces.doc_labels import DocLabelColors

from paperwork_gtk.interfaces.widgets import LabelFactory


class LabelWidget(Gtk.DrawingArea):
    FONT = ""
    LABEL_HEIGHT = 23
    LABEL_TEXT_SIZE = 13
    LABEL_TEXT_SHIFT = 3    # Shift a bit to fix valignment
    LABEL_CORNER_RADIUS = 5

    def __init__(self, core, label_txt, label_color, highlight=False):
        super().__init__()
        self.core = core
        self.txt = label_txt
        self.color = label_color
        self.highlight = highlight
        self.connect("draw", self._draw)

        # we must compute the widget size
        dummy = cairo.ImageSurface(cairo.Format.RGB24, 200, 200)
        ctx = cairo.Context(dummy)
        size = self.compute_size(ctx)
        dummy.finish()

        self.set_size_request(size[0], size[1])

    def compute_size(self, cairo_ctx):
        cairo_ctx.set_font_size(self.LABEL_TEXT_SIZE)
        if not self.highlight:
            cairo_ctx.select_font_face(
                self.FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
        else:
            cairo_ctx.select_font_face(
                self.FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD
            )

        (p_x1, p_y1, p_x2, p_y2, p_x3, p_y3) = cairo_ctx.text_extents(
            self.txt
        )
        return (
            p_x3 - p_x1 + (2 * self.LABEL_CORNER_RADIUS),
            self.LABEL_HEIGHT
        )

    @staticmethod
    def _rectangle_rounded(cairo_ctx, area, radius):
        (x, y, w, h) = area
        cairo_ctx.new_sub_path()
        cairo_ctx.arc(
            x + w - radius, y + radius,
            radius, -1.0 * math.pi / 2, 0
        )
        cairo_ctx.arc(
            x + w - radius, y + h - radius,
            radius, 0, math.pi / 2
        )
        cairo_ctx.arc(
            x + radius, y + h - radius, radius,
            math.pi / 2, math.pi
        )
        cairo_ctx.arc(
            x + radius, y + radius, radius,
            math.pi, 3.0 * math.pi / 2
        )
        cairo_ctx.close_path()

    def _draw(self, _, cairo_ctx):
        txt_offset = (
            (self.LABEL_HEIGHT - self.LABEL_TEXT_SIZE) / 2 +
            self.LABEL_TEXT_SHIFT
        )

        (w, h) = self.compute_size(cairo_ctx)

        # background rectangle
        bg = self.color
        cairo_ctx.set_source_rgb(bg[0], bg[1], bg[2])
        cairo_ctx.set_line_width(1)
        self._rectangle_rounded(
            cairo_ctx,
            (0, 0, w, h),
            self.LABEL_CORNER_RADIUS
        )
        cairo_ctx.fill()

        # foreground text
        fg = self.core.call_success(DocLabelColors.label_get_foreground_color, self.color)
        cairo_ctx.set_source_rgb(fg[0], fg[1], fg[2])
        cairo_ctx.move_to(
            self.LABEL_CORNER_RADIUS,
            h - txt_offset
        )
        cairo_ctx.text_path(self.txt)
        cairo_ctx.fill()


if GTK_AVAILABLE:
    GObject.type_register(LabelWidget)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    LabelFactory,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": DocLabelColors,
                "defaults": ["paperwork_backend.model.labels"],
            }
        ]

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'] = openpaperwork_core.deps.CAIRO
        if not GI_AVAILABLE:
            out['gi'] = openpaperwork_core.deps.GI
        if not GTK_AVAILABLE:
            out['gtk'] = openpaperwork_gtk.deps.GTK

    def gtk_widget_label_new(self, label_txt, label_color, highlight=False):
        assert CAIRO_AVAILABLE
        assert GI_AVAILABLE
        assert GTK_AVAILABLE
        return LabelWidget(self.core, label_txt, label_color, highlight)
