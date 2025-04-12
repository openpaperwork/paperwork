import collections
import logging
import math
import random
import statistics

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.widgets import GtkChartLines
import openpaperwork_gtk.deps

from openpaperwork_gtk import _


GI_AVAILABLE = False
GTK_AVAILABLE = False
PANGO_AVAILABLE = False

try:
    import gi
    from gi.repository import GObject
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        gi.require_version('Gdk', '3.0')
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gdk
        from gi.repository import Gtk
        GTK_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        gi.require_version('Pango', '1.0')
        gi.require_version('PangoCairo', '1.0')
        from gi.repository import Pango
        from gi.repository import PangoCairo
        PANGO_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)
SUM_COLOR = (0, 0, 0)


class Schema:
    def __init__(
            self,
            column_value_id_idx,
            column_line_id_idx,
            column_axis_x_values_idx,
            column_axis_x_names_idx,
            column_axis_y_values_idx,
            column_axis_y_names_idx,
            highlight_x_range=(math.inf, -math.inf)):
        self.column_value_id_idx = column_value_id_idx
        self.column_line_id_idx = column_line_id_idx
        self.column_axis_x_values_idx = column_axis_x_values_idx
        self.column_axis_x_names_idx = column_axis_x_names_idx
        self.column_axis_y_values_idx = column_axis_y_values_idx
        self.column_axis_y_names_idx = column_axis_y_names_idx
        self.highlight_x_range = highlight_x_range


class ColorGenerator:
    def __init__(self):
        self.colors = []
        self.color_idx = -1

    def reset(self):
        self.color_idx = -1

    def __next__(self):
        self.color_idx += 1
        if self.color_idx >= len(self.colors):
            self.colors.append((
                random.randint(0, 0xFF) / 0xFF,
                random.randint(0, 0xFF) / 0xFF,
                random.randint(0, 0xFF) / 0xFF,
            ))
        return self.colors[self.color_idx]


class DrawContext:
    """
    Custom drawing context around cairo context, so we can change
    the scale without changing the line width.
    """
    def __init__(self, ctx):
        self.ctx = ctx

    def get_cairo(self):
        if hasattr(self.ctx, 'get_cairo'):
            return self.ctx.get_cairo()
        return self.ctx

    def translate_pt(self, pt_x, pt_y):
        return (pt_x, pt_y)

    def untranslate_pt(self, pt_x, pt_y):
        return (pt_x, pt_y)

    def distance(self, pt_a_x, pt_a_y, pt_b_x, pt_b_y):
        d_x = abs(pt_a_x - pt_b_x)
        d_y = abs(pt_a_y - pt_b_y)
        return (d_x ** 2) + (d_y ** 2)

    def arc(self, x, y, radius, angle1, angle2):
        self.ctx.arc(x, y, radius, angle1, angle2)

    def save(self):
        self.ctx.save()

    def restore(self):
        self.ctx.restore()

    def set_source_rgb(self, r, g, b):
        self.ctx.set_source_rgb(r, g, b)

    def set_source_rgba(self, r, g, b, a):
        self.ctx.set_source_rgba(r, g, b, a)

    def set_line_width(self, line_width):
        self.ctx.set_line_width(line_width)

    def move_to(self, pt_x, pt_y):
        self.ctx.move_to(pt_x, pt_y)

    def line_to(self, pt_x, pt_y):
        self.ctx.line_to(pt_x, pt_y)

    def rectangle(self, x, y, w, h):
        self.ctx.rectangle(x, y, w, h)

    def stroke(self):
        self.ctx.stroke()

    def fill(self):
        self.ctx.fill()

    def translate(self, x, y):
        return DrawContextTranslated(self, x, y)

    def scale(self, x, y):
        return DrawContextScaled(self, x, y)


class DrawContextTranslated(DrawContext):
    def __init__(self, ctx, translation_x, translation_y):
        super().__init__(ctx)
        self.x = translation_x
        self.y = translation_y

    def translate_pt(self, pt_x, pt_y):
        (pt_x, pt_y) = (pt_x + self.x, pt_y + self.y)
        return self.ctx.translate_pt(pt_x, pt_y)

    def untranslate_pt(self, pt_x, pt_y):
        (pt_x, pt_y) = self.ctx.untranslate_pt(pt_x, pt_y)
        return (pt_x - self.x, pt_y - self.y)

    def distance(
            self,
            pt_untranslated_x, pt_untranslated_y,
            pt_translated_x, pt_translated_y):
        pt_a_x = pt_untranslated_x + self.x
        pt_a_y = pt_untranslated_y + self.y
        return self.ctx.distance(
            pt_a_x, pt_a_y,
            pt_translated_x, pt_translated_y,
        )

    def arc(self, x, y, radius, angle1, angle2):
        self.ctx.arc(x + self.x, y + self.y, radius, angle1, angle2)

    def move_to(self, pt_x, pt_y):
        self.ctx.move_to(pt_x + self.x, pt_y + self.y)

    def line_to(self, pt_x, pt_y):
        self.ctx.line_to(pt_x + self.x, pt_y + self.y)

    def rectangle(self, x, y, w, h):
        self.ctx.rectangle(x + self.x, y + self.y, w, h)


class DrawContextScaled(DrawContext):
    def __init__(self, ctx, scale_x, scale_y):
        super().__init__(ctx)
        self.x = scale_x
        self.y = scale_y

    def translate_pt(self, pt_x, pt_y):
        (pt_x, pt_y) = (pt_x * self.x, pt_y * self.y)
        return self.ctx.translate_pt(pt_x, pt_y)

    def untranslate_pt(self, pt_x, pt_y):
        (pt_x, pt_y) = self.ctx.untranslate_pt(pt_x, pt_y)
        return (pt_x / self.x, pt_y / self.y)

    def distance(
            self,
            pt_unscaled_x, pt_unscaled_y,
            pt_scaled_x, pt_scaled_y):
        pt_a_x = pt_unscaled_x * self.x
        pt_a_y = pt_unscaled_y * self.y
        return self.ctx.distance(
            pt_a_x, pt_a_y,
            pt_scaled_x, pt_scaled_y,
        )

    def arc(self, x, y, radius, angle1, angle2):
        self.ctx.arc(x * self.x, y * self.y, radius, angle1, angle2)

    def move_to(self, pt_x, pt_y):
        self.ctx.move_to(pt_x * self.x, pt_y * self.y)

    def line_to(self, pt_x, pt_y):
        self.ctx.line_to(pt_x * self.x, pt_y * self.y)

    def rectangle(self, x, y, w, h):
        self.ctx.rectangle(x * self.x, y * self.y, w * self.x, h * self.y)


class Point:
    RADIUS = 2
    LABEL_LINE_HEIGHT = 14

    def __init__(self, liststore_idx, x, y, label_x, label_y, color):
        self.liststore_idx = liststore_idx
        self.x = x
        self.y = y
        self.label_x = label_x
        self.label_y = label_y
        self.color = color

    def copy(self):
        return Point(
            self.liststore_idx,
            self.x, self.y,
            self.label_x, self.label_y,
            self.color
        )

    def __lt__(self, other):
        if self.x < other.x:
            return True
        if self.y < other.y:
            return True
        return False

    @staticmethod
    def merge(pts):
        merged_pt = pts[0].copy()
        merged_pt.y = statistics.mean([p.y for p in pts])
        merged_pt.label_y = "\n".join([p.label_y for p in pts])
        return merged_pt

    @staticmethod
    def merge_same_x(all_pts):
        pack = []
        last_x = None
        pts = []
        for pt in all_pts:
            if last_x is None:
                pack.append(pt)
                last_x = pt.x
            elif last_x == pt.x:
                pack.append(pt)
            else:
                pts.append(Point.merge(pack))
                last_x = pt.x
                pack = [pt]
        if len(pack) > 0:
            pts.append(Point.merge(pack))
        return pts

    @staticmethod
    def from_liststore_line(liststore_idx, line, schema, color):
        return Point(
            liststore_idx,
            line[schema.column_axis_x_values_idx],
            line[schema.column_axis_y_values_idx],
            line[schema.column_axis_x_names_idx],
            line[schema.column_axis_y_names_idx],
            color
        )

    def draw_label_x(self, widget_size, draw_ctx):
        height = (self.label_x.count("\n") + 1) * self.LABEL_LINE_HEIGHT

        cairo_ctx = draw_ctx.get_cairo()
        x = draw_ctx.translate_pt(self.x, widget_size[1] - self.y)[0]
        widget_size = draw_ctx.translate_pt(widget_size[0], widget_size[1])

        layout = PangoCairo.create_layout(cairo_ctx)
        layout.set_text(self.label_x, -1)

        txt_size = layout.get_size()
        if 0 in txt_size:
            return

        cairo_ctx.save()
        try:
            txt_scale = height / txt_size[1]
            txt_width = txt_size[0] * txt_scale
            if x <= widget_size[0] / 2:
                x += 5
            else:
                x -= (txt_width + 10)

            cairo_ctx.set_source_rgb(0, 0, 0)
            cairo_ctx.translate(x, 0)
            cairo_ctx.scale(txt_scale * Pango.SCALE, txt_scale * Pango.SCALE)
            PangoCairo.update_layout(cairo_ctx, layout)
            PangoCairo.show_layout(cairo_ctx, layout)
        finally:
            cairo_ctx.restore()

    def draw_label_y(self, widget_size, draw_ctx):
        height = (self.label_y.count("\n") + 1) * self.LABEL_LINE_HEIGHT

        cairo_ctx = draw_ctx.get_cairo()
        y = draw_ctx.translate_pt(self.x, widget_size[1] - self.y)[1]
        widget_size = draw_ctx.translate_pt(widget_size[0], widget_size[1])

        layout = PangoCairo.create_layout(cairo_ctx)
        layout.set_text(self.label_y, -1)

        txt_size = layout.get_size()
        if 0 in txt_size:
            return

        cairo_ctx.save()
        try:
            txt_scale = height / txt_size[1]
            if y <= widget_size[1] / 2:
                y += 2
            else:
                y -= (height + 2)
            cairo_ctx.set_source_rgb(0, 0, 0)
            cairo_ctx.translate(0, y)
            cairo_ctx.scale(txt_scale * Pango.SCALE, txt_scale * Pango.SCALE)
            PangoCairo.update_layout(cairo_ctx, layout)
            PangoCairo.show_layout(cairo_ctx, layout)
        finally:
            cairo_ctx.restore()

    def draw_highlight(self, widget_size, draw_ctx):
        draw_ctx.set_source_rgb(0.57, 0.7, 0.837)
        draw_ctx.set_line_width(1)

        # TODO(Jflesch): we should use the real widget size, and not
        # the widget size relative to point (0, 0)
        draw_ctx.move_to(-widget_size[0] * 2, widget_size[1] - self.y)
        draw_ctx.line_to(widget_size[0] * 2, widget_size[1] - self.y)
        draw_ctx.stroke()

        # TODO(Jflesch): we should use the real widget size, and not
        # the widget size relative to point (0, 0)
        draw_ctx.move_to(self.x, -widget_size[1] * 2)
        draw_ctx.line_to(self.x, widget_size[1] * 2)
        draw_ctx.stroke()

        self.draw_label_x(widget_size, draw_ctx)
        self.draw_label_y(widget_size, draw_ctx)

    def distance(self, widget_size, draw_ctx, x, y):
        return draw_ctx.distance(self.x, widget_size[1] - self.y, x, y)


class Line:
    LEGEND_CIRCLE_RADIUS = 8
    LEGEND_LINE_HEIGHT = 16
    LEGEND_SPACING = 8

    def __init__(self, line_name, points, color, line_width=1.0):
        self.line_name = line_name
        self.points = points
        self.points.sort(key=lambda pt: pt.x)
        self.color = color
        self.minmax = ((math.inf, 0), (0, 0))
        self.line_width = line_width
        for pt in points:
            self.minmax = (
                (
                    min(self.minmax[0][0], pt.x),
                    max(self.minmax[0][1], pt.x),
                ),
                (
                    min(self.minmax[1][0], pt.y),
                    max(self.minmax[1][1], pt.y),
                ),
            )

    @staticmethod
    def from_liststore_lines(line_name, liststore_lines, schema, color):
        pts = [
            Point.from_liststore_line(liststore_idx, line, schema, color)
            for (liststore_idx, line) in liststore_lines
        ]
        pts = Point.merge_same_x(pts)
        return Line(line_name, pts, color)

    @staticmethod
    def make_line_sum(other_lines):
        pts = []
        for line in other_lines:
            pts += [
                (line.line_name, pt.copy())
                for pt in line.points
            ]
        pts.sort(key=lambda pt: pt[1].x)

        total_txt = _("Total: {}")

        last_y = collections.defaultdict(lambda: 0)
        for (line_name, pt) in pts:
            last_y[line_name] = pt.y
            pt.y = sum(last_y.values())
            pt.label_y = total_txt.format(pt.y)

        pts = [pt for (line_name, pt) in pts]
        pts = Point.merge_same_x(pts)
        return Line(_("Total"), pts, SUM_COLOR, 2.0)

    def draw_chart(self, widget_size, draw_ctx):
        draw_ctx.save()
        try:
            draw_ctx.set_line_width(self.line_width)
            draw_ctx.set_source_rgb(*self.color)
            for (idx, pt) in enumerate(self.points):
                if idx == 0:
                    draw_ctx.move_to(pt.x, widget_size[1] - pt.y)
                else:
                    draw_ctx.line_to(pt.x, widget_size[1] - pt.y)
            draw_ctx.stroke()
        finally:
            draw_ctx.restore()

    def draw_legend(self, widget_size, cairo_ctx, x, y):
        layout = PangoCairo.create_layout(cairo_ctx)
        layout.set_text(self.line_name, -1)
        txt_size = layout.get_size()
        if 0 in txt_size:
            return (x, y)

        cairo_ctx.save()
        try:
            txt_scale = self.LEGEND_LINE_HEIGHT / txt_size[1]

            txt_width = txt_size[0] * txt_scale
            width = txt_width
            width += 2 * self.LEGEND_CIRCLE_RADIUS
            width += 2 * self.LEGEND_SPACING
            if x + width >= widget_size[0]:
                y += self.LEGEND_LINE_HEIGHT + self.LEGEND_SPACING
                x = 0

            cairo_ctx.set_source_rgb(*self.color)
            cairo_ctx.arc(
                x + self.LEGEND_CIRCLE_RADIUS,
                y + self.LEGEND_CIRCLE_RADIUS,
                self.LEGEND_CIRCLE_RADIUS,
                0, math.pi * 2
            )
            cairo_ctx.fill()
            x += (2 * self.LEGEND_CIRCLE_RADIUS) + self.LEGEND_SPACING

            cairo_ctx.set_source_rgb(0.0, 0.0, 0.0)
            cairo_ctx.translate(x, y)
            cairo_ctx.scale(txt_scale * Pango.SCALE, txt_scale * Pango.SCALE)
            PangoCairo.update_layout(cairo_ctx, layout)
            PangoCairo.show_layout(cairo_ctx, layout)

            x += txt_width + self.LEGEND_SPACING
        finally:
            cairo_ctx.restore()
        return (x, y)

    def get_closest_point(self, widget_size, draw_ctx, x, y):
        return min((
            (point.distance(widget_size, draw_ctx, x, y), point)
            for point in self.points
        ), default=None)


class Lines:
    HIGHLIGHT_COLOR = (0.5, 0.5, 0.5, 0.5)

    def __init__(self, schema, liststore, color_generator):
        self.schema = schema
        self.liststore = liststore
        self.color_generator = color_generator
        self.active_point = None

        self.lines = []
        self.minmax = ((math.inf, 0), (0, 0),)

    def reset(self):
        self.lines = []

    def reload(self):
        self.minmax = ((math.inf, 0), (0, 0),)
        self.color_generator.reset()
        lines = collections.defaultdict(list)
        for (liststore_idx, line) in enumerate(self.liststore):
            line_name = line[self.schema.column_line_id_idx]
            lines[line_name].append((liststore_idx, line))
        self.lines = [
            Line.from_liststore_lines(
                k, v, self.schema, next(self.color_generator)
            )
            for (k, v) in lines.items()
        ]
        if len(self.lines) > 1:
            self.lines = [Line.make_line_sum(self.lines)] + self.lines
        for line in self.lines:
            self.minmax = (
                (
                    min(self.minmax[0][0], line.minmax[0][0]),
                    max(self.minmax[0][1], line.minmax[0][1]),
                ),
                (
                    min(self.minmax[1][0], line.minmax[1][0]),
                    max(self.minmax[1][1], line.minmax[1][1]),
                ),
            )

    def draw_chart_highlight(self, widget_size, draw_ctx):
        x_range = self.schema.highlight_x_range
        if x_range[1] <= x_range[0]:
            return
        if x_range[0] is -math.inf:
            x_range = (self.minmax[0][0], self.x_range[1])
        if x_range[1] is math.inf:
            x_range = (x_range[0], self.minmax[0][1])
        x_range = (
            (
                x_range[0] - self.minmax[0][0]
            ) / (
                self.minmax[0][1] - self.minmax[0][0]
            ),
            (
                x_range[1] - self.minmax[0][0]
            ) / (
                self.minmax[0][1] - self.minmax[0][0]
            ),
        )
        x_range = (x_range[0] * widget_size[0], x_range[1] * widget_size[0])

        draw_ctx.save()
        try:
            draw_ctx.set_source_rgba(*self.HIGHLIGHT_COLOR)
            draw_ctx.rectangle(
                int(x_range[0]) + 1, 0, x_range[1] - x_range[0], widget_size[1]
            )
            draw_ctx.fill()
        finally:
            draw_ctx.restore()

    def draw_chart(self, widget_size, draw_ctx):
        w = self.minmax[0][1] - self.minmax[0][0]
        h = self.minmax[1][1] - self.minmax[1][0]

        if w == 0 or h == 0:
            return

        draw_ctx = draw_ctx.scale(widget_size[0] / w, widget_size[1] / h)
        widget_size = (w, h)

        self.draw_chart_highlight(widget_size, draw_ctx)

        draw_ctx = draw_ctx.translate(
            -self.minmax[0][0], min(0, self.minmax[1][0])
        )
        widget_size = (widget_size[0] + self.minmax[0][0], widget_size[1])

        draw_ctx.save()
        try:
            for line in self.lines:
                line.draw_chart(widget_size, draw_ctx)
        finally:
            draw_ctx.restore()
        if self.active_point is not None:
            self.active_point.draw_highlight(widget_size, draw_ctx)

    def draw_legend(self, widget_size, cairo_ctx):
        x = 0
        y = 0
        for line in self.lines:
            (x, y) = line.draw_legend(widget_size, cairo_ctx, x, y)
        return (x, y)

    def get_closest_point(self, widget_size, draw_ctx, x, y):
        w = self.minmax[0][1] - self.minmax[0][0]
        h = self.minmax[1][1] - self.minmax[1][0]

        if w == 0 or h == 0:
            return None

        draw_ctx = draw_ctx.scale(widget_size[0] / w, widget_size[1] / h)
        widget_size = (w, h)

        draw_ctx = draw_ctx.translate(
            -self.minmax[0][0], min(0, self.minmax[1][0])
        )
        widget_size = (widget_size[0] - self.minmax[0][0], widget_size[1])

        return min((
            line.get_closest_point(widget_size, draw_ctx, x, y)
            for line in self.lines
        ), default=None)


class ChartDrawer:
    MARGIN = 5

    def __init__(self, core, schema, liststore, color_generator):
        self.core = core
        self.lines = Lines(schema, liststore, color_generator)

        self.chart_widget = Gtk.DrawingArea.new()
        self.chart_widget.set_size_request(-1, 200)
        self.chart_widget.set_visible(True)
        self.chart_widget.connect("draw", self.draw_chart)
        self.chart_widget.connect("realize", self._on_chart_realized)
        self.chart_widget.connect("motion-notify-event", self._on_mouse_motion)

        self.legend_widget = Gtk.DrawingArea.new()
        self.legend_widget.set_visible(True)
        self.legend_widget.connect("draw", self.draw_legend)

        liststore.connect("row-changed", self.reload)
        liststore.connect("row-deleted", self.reload)
        liststore.connect("row-inserted", self.reload)
        liststore.connect("rows-reordered", self.reload)

        self._on_chart_realized()

        self.has_changed = False
        self.reload_planned = False
        self._reload()

    def _on_chart_realized(self, *args, **kwargs):
        mask = Gdk.EventMask.POINTER_MOTION_MASK
        self.chart_widget.add_events(mask)
        if self.chart_widget.get_window() is not None:
            self.chart_widget.get_window().set_events(
                self.chart_widget.get_window().get_events() | mask
            )

    def reload(self, *args, **kwargs):
        self.lines.reset()
        self.chart_widget.queue_draw()
        self.legend_widget.queue_draw()
        if self.reload_planned:
            self.has_changed = True
        else:
            self.has_changed = False
            self.reload_planned = True
            promise = openpaperwork_core.promise.DelayPromise(
                self.core, delay_s=0.25
            )
            promise.then(self._reload)
            promise.schedule()

    def _reload(self):
        self.reload_planned = False
        if self.has_changed:
            self.reload()
            return
        self.lines.reload()
        self.chart_widget.queue_draw()
        self.legend_widget.queue_draw()

    def _on_mouse_motion(self, widget, event):
        draw_ctx = DrawContext(None)
        draw_ctx = draw_ctx.translate(self.MARGIN, self.MARGIN)
        widget_size = (
            widget.get_allocated_width() - (2 * self.MARGIN),
            widget.get_allocated_height() - (2 * self.MARGIN),
        )
        r = self.lines.get_closest_point(
            widget_size, draw_ctx, event.x, event.y
        )
        if r is None:
            self.lines.active_point = None
            return
        (dist, point) = r
        if self.lines.active_point is not point:
            self.lines.active_point = point
            self.chart_widget.queue_draw()

    def draw_chart(self, widget, cairo_ctx):
        widget_size = (
            widget.get_allocated_width() - (2 * self.MARGIN),
            widget.get_allocated_height() - (2 * self.MARGIN),
        )
        draw_ctx = DrawContext(cairo_ctx)
        draw_ctx = draw_ctx.translate(self.MARGIN, self.MARGIN)
        self.lines.draw_chart(widget_size, draw_ctx)

    def draw_legend(self, widget, cairo_ctx):
        widget_size = (
            widget.get_allocated_width() - (2 * self.MARGIN),
            widget.get_allocated_height() - (2 * self.MARGIN),
        )
        cairo_ctx.translate(self.MARGIN, self.MARGIN)
        (x, y) = self.lines.draw_legend(widget_size, cairo_ctx)
        if x > 0:
            # the y we got is relative to the top of the current line.
            # the height is starting at the bottom of the current line.
            y += Line.LEGEND_SPACING + Line.LEGEND_LINE_HEIGHT
        if y + self.MARGIN != widget_size[1]:
            widget.set_size_request(-1, y + self.MARGIN)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    GtkChartLines,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps()

    def __init__(self, core):
        super().__init__(core)
        self.color_generator = ColorGenerator()

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)
        if not PANGO_AVAILABLE:
            out['pango'].update(openpaperwork_core.deps.PANGO)

    def gtk_charts_lines_get(
            self, liststore, *args, **kwargs):
        """
        Return a Gtk.Widget showing the specified line chart.

        Can display multiple lines on single chart.
        In the model, each row is a value (x, y) for a given line.

        Arguments:
        - model: Gtk.ListStore to use as model
        - column_value_id_idx: column in the model that contains the value IDs.
        - column_line_id_idx: column that contains the name of the line
          to which this value belongs.
        - column_axis_x_values_idx: column that contains the values for the X
          axis. Must contain integers, floats or doubles.
        - column_axis_x_names_idx: column that contains the names corresponding
          to the values on the X axis. Must be strings.
        - column_axis_y_values_idx: column that contains the values for the Y
          axis. Must contain integers, floats or doubles.
        - column_axis_y_names_idx: column that contains the names corresponding
          toi the values on the Y axis. Must be strings
        """
        schema = Schema(*args, **kwargs)
        return ChartDrawer(self.core, schema, liststore, self.color_generator)


if __name__ == "__main__":
    model = Gtk.ListStore.new((
        GObject.TYPE_STRING,  # value id
        GObject.TYPE_STRING,  # line id
        GObject.TYPE_INT64,  # value X
        GObject.TYPE_INT64,  # value Y
        GObject.TYPE_STRING,  # name X
        GObject.TYPE_STRING,  # name Y
    ))
    model_content = (
        ("value A55", "line A", 5, 5, "A5", "A5"),
        ("value B55", "line B", 5, 5, "B5", "B5"),
        ("value A67", "line A", 6, 7, "A6", "A7"),
        ("value B66", "line B", 6, 6, "B6", "B6"),
        # graph must support having many values at the same position in X
        ("value A77", "line A", 7, 7, "A7", "A7"),
        ("value A73", "line A", 7, 3, "A7", "A3"),
        ("value A79", "line A", 7, 9, "A7", "A9"),
        ("value B79", "line B", 7, 9, "B7", "B9"),
        ("value A83", "line A", 8, 3, "A8", "A3"),
        ("value B88", "line B", 8, 8, "B8", "B8"),
        ("value A97", "line A", 9, 7, "A9", "A7"),
        ("value B95", "line B", 9, 5, "B9", "B5"),
        ("value A10-5", "line A", 10, -5, "A10", "A-5"),
        ("value B910", "line B", 9, 10, "B9", "B10"),
    )
    model.clear()
    for line in model_content:
        model.append(line)

    core = openpaperwork_core.Core()
    core.load("openpaperwork_gtk.widgets.charts.lines")
    core.init()

    chart_lines = core.call_success(
        GtkChartLines.gtk_charts_lines_get, model,
        column_value_id_idx=0,
        column_line_id_idx=1,
        column_axis_x_values_idx=2,
        column_axis_y_values_idx=3,
        column_axis_x_names_idx=4,
        column_axis_y_names_idx=5
    )

    window = Gtk.Window()
    window.set_default_size(600, 600)
    window.add(chart_lines.chart_widget)
    window.show_all()

    window_legend = Gtk.Window()
    window_legend.set_default_size(100, 100)
    window_legend.add(chart_lines.legend_widget)
    window_legend.show_all()

    Gtk.main()
