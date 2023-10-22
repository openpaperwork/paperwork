import collections
import logging

try:
    from gi.repository import GObject
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    # workaround so chkdeps can still be called
    class Gtk(object):
        class Box(object):
            pass

        class Widget(object):
            pass

    GTK_AVAILABLE = False


import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class WidgetInfo(object):
    def __init__(self, widget, alignment, size=None):
        self.widget = widget
        self.alignment = alignment
        if size is not None:
            self.size = (int(size[0]), int(size[1]))
        else:
            self.size = (0, 0)
        self.position = (-1, -1)
        self.visible = False

    def update_widget_size(self):
        if self.widget is None:  # test mode
            return
        self.size = (
            self.widget.get_preferred_width()[0],
            self.widget.get_preferred_height()[0],
        )

    def is_visible(self):
        if self.widget is None:  # test mode
            return True
        return self.widget.get_visible()

    def __eq__(self, o):
        if self is o:
            return True
        return self.widget == o


def recompute_height_for_width(widgets, width, spacing=(0, 0)):
    height = spacing[1]
    line_height = 0
    line_width = 0
    for widget in widgets:
        if not widget.is_visible():
            continue
        if widget.size == (0, 0):
            widget.update_widget_size()
        if line_width + widget.size[0] + spacing[0] > width + 1:
            height += spacing[1]
            height += line_height
            line_width = 0
            line_height = 0
        line_width += spacing[0]
        line_width += widget.size[0]
        line_height = max(line_height, widget.size[1])
    height += line_height
    height += spacing[1]
    return height


def recompute_box_positions(core, widgets, width, spacing=(0, 0)):
    core.call_all("on_perfcheck_start", "recompute_box_positions")

    # build lines
    lines = []
    line_heights = []
    line = []
    line_width = spacing[0]
    max_line_width = 0
    line_height = 0
    for widget in widgets:
        if not widget.is_visible():
            continue
        widget.update_widget_size()
        if line_width + widget.size[0] + spacing[0] > width + 1:
            lines.append(line)
            line_heights.append(line_height)
            line = []
            max_line_width = max(max_line_width, line_width)
            line_width = 0
            line_height = 0
        line.append(widget)
        line_width += spacing[0]
        line_width += widget.size[0]
        line_height = max(line_height, widget.size[1])
    max_line_width = max(max_line_width, line_width)
    lines.append(line)
    line_heights.append(line_height)

    # sort widgets by alignment in each line
    def sort_widgets_per_alignments(widgets):
        out = {
            Gtk.Align.START: [],
            Gtk.Align.CENTER: [],
            Gtk.Align.END: [],
        }
        for widget in widgets:
            out[widget.alignment].append(widget)
        return out

    lines = [sort_widgets_per_alignments(line) for line in lines]

    # position widgets in lines
    height = spacing[1]
    for (line, line_height) in zip(lines, line_heights):
        nb_columns = 0
        w_start = 0
        w_end = width

        # start
        for widget in line[Gtk.Align.START]:
            nb_columns += 1
            w_start += spacing[0]
            widget.position = (w_start, height)
            w_start += widget.size[0]

        # end
        line[Gtk.Align.END].reverse()
        for widget in line[Gtk.Align.END]:
            nb_columns += 1
            w_end -= spacing[0]
            w_end -= widget.size[0]
            widget.position = (w_end, height)

        # center
        w_center = sum(w.size[0] for w in line[Gtk.Align.CENTER])
        w_center += spacing[0] * (len(line[Gtk.Align.CENTER]) - 1)
        w_center = (width - w_center) / 2
        w_orig = w_center
        for widget in line[Gtk.Align.CENTER]:
            nb_columns += 1
            if w_center != w_orig:
                w_center += spacing[0]
            widget.position = (int(w_center), int(height))
            w_center += widget.size[0]

        height += line_height
        height += spacing[1]

    core.call_all(
        "on_perfcheck_stop", "recompute_box_positions",
        nb_boxes=len(widgets)
    )
    return (widgets, max_line_width, height)


class CustomFlowLayout(Gtk.Box):
    def __init__(self, core, spacing=(0, 0)):
        super().__init__()
        self.core = core

        self.widgets = collections.OrderedDict()

        self.spacing = spacing
        self.vadjustment = None
        self.bottom_margin = 0
        self.allocation = None

        self.set_has_window(False)
        self.set_redraw_on_allocate(False)

        self.connect("size-allocate", self._on_size_allocate)
        self.connect("add", self._on_add)
        self.connect("remove", self._on_remove)

    def _on_add(self, _, widget):
        self.recompute_layout()
        self.queue_resize()

    def _on_remove(self, _, widget):
        self.widgets.pop(widget)
        self.queue_draw()
        self.queue_resize()

    def do_forall(self, include_internals: bool, callback, callback_data=None):
        if not hasattr(self, 'widgets'):
            return
        widgets = self.widgets.copy()
        for widget in widgets:
            callback(widget)

    def add_child(self, widget, alignment):
        w = WidgetInfo(widget, alignment)
        self.widgets[widget] = w
        self.add(widget)

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.WIDTH_FOR_HEIGHT

    def do_get_preferred_width(self):
        nat_width = 0
        for widget in self.widgets.values():
            widget.update_widget_size()
            nat_width += widget.size[0]
        return (0, nat_width)

    def do_get_preferred_height_for_width(self, width):
        requested_height = recompute_height_for_width(
            self.widgets.values(), width, self.spacing
        )
        requested_height += self.bottom_margin
        return (requested_height, requested_height)

    def do_get_preferred_height(self):
        (min_width, nat_width) = self.do_get_preferred_width()
        return self.do_get_preferred_height_for_width(min_width)

    def do_get_preferred_width_for_height(self, height):
        return self.do_get_preferred_width()

    def _on_size_allocate(self, _, allocation):
        self.allocation = allocation
        self.recompute_layout()

    def recompute_layout(self):
        if self.allocation is None:
            return

        for widget in self.widgets.values():
            widget.update_widget_size()

        (
            _, self.requested_width, self.requested_height
        ) = recompute_box_positions(
            self.core, self.widgets.values(), self.allocation.width,
            self.spacing
        )
        self.requested_height += self.bottom_margin

        for widget in self.widgets.values():
            rect = Gdk.Rectangle()
            rect.x = self.allocation.x + widget.position[0]
            rect.y = self.allocation.y + widget.position[1]
            rect.width = widget.size[0]
            rect.height = widget.size[1]
            widget.widget.size_allocate(rect)

    def _on_destroy(self, _):
        if not hasattr(self, 'widgets'):
            return
        for widget in self.widgets.keys():
            widget.unparent()
        self.widgets = collections.OrderedDict()

    def set_bottom_margin(self, height):
        self.bottom_margin = height
        self.queue_resize()


if GTK_AVAILABLE:
    GObject.type_register(CustomFlowLayout)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_widget_flowlayout',
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def gtk_widget_flowlayout_new(self, spacing=(0, 0)):
        assert GLIB_AVAILABLE
        assert GTK_AVAILABLE
        return CustomFlowLayout(self.core, spacing)
