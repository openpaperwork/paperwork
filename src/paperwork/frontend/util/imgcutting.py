#   Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2013-2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GObject

from paperwork.frontend.util.canvas.drawers import Drawer
from paperwork.frontend.util.canvas.drawers import PillowImageDrawer


class ImgGrip(Drawer):

    """
    Represents one of the grip that user can move to cut an image.
    """

    layer = Drawer.BOX_LAYER

    GRIP_SIZE = 40
    DEFAULT_COLOR = (0.0, 0.0, 1.0)
    HOVER_COLOR = (0.0, 1.0, 0.0)
    SELECTED_COLOR = (1.0, 0.0, 0.0)

    def __init__(self, position, max_position):
        self._img_position = position
        self.max_position = max_position
        self.size = (0, 0)
        self.scale = 1.0
        self.selected = False
        self.hover = False
        self.visible = True

    def __get_img_position(self):
        return self._img_position

    def __set_img_position(self, position):
        self._img_position = (
            min(max(0, position[0]), self.max_position[0]),
            min(max(0, position[1]), self.max_position[1]),
        )

    img_position = property(__get_img_position, __set_img_position)

    def __get_on_screen_pos(self):
        x = int(self.scale * self._img_position[0])
        y = int(self.scale * self._img_position[1])
        return (x, y)

    position = property(__get_on_screen_pos)

    def __get_select_area(self):
        (x, y) = self.__get_on_screen_pos()
        x_min = x - (self.GRIP_SIZE / 2)
        y_min = y - (self.GRIP_SIZE / 2)
        x_max = x + (self.GRIP_SIZE / 2)
        y_max = y + (self.GRIP_SIZE / 2)
        return ((x_min, y_min), (x_max, y_max))

    def is_on_grip(self, position):
        """
        Indicates if position is on the grip

        Arguments:
            position --- tuple (int, int)
            scale --- Scale at which the image is represented

        Returns:
            True or False
        """
        ((x_min, y_min), (x_max, y_max)) = self.__get_select_area()
        return (x_min <= position[0] and position[0] <= x_max
                and y_min <= position[1] and position[1] <= y_max)

    def do_draw(self, cairo_ctx):
        if not self.visible:
            return
        ((a_x, a_y), (b_x, b_y)) = self.__get_select_area()
        a_x -= self.canvas.offset[0]
        a_y -= self.canvas.offset[1]
        b_x -= self.canvas.offset[0]
        b_y -= self.canvas.offset[1]

        if self.selected:
            color = self.SELECTED_COLOR
        elif self.hover:
            color = self.HOVER_COLOR
        else:
            color = self.DEFAULT_COLOR
        cairo_ctx.set_source_rgb(color[0], color[1], color[2])
        cairo_ctx.set_line_width(1.0)
        cairo_ctx.rectangle(a_x, a_y, b_x - a_x, b_y - a_y)
        cairo_ctx.stroke()


class ImgGripRectangle(Drawer):
    layer = (Drawer.BOX_LAYER + 1)  # draw below/before the grips itself

    COLOR = (0.0, 0.0, 1.0)

    def __init__(self, grips):
        self.grips = grips

    def __get_size(self):
        positions = [grip.position for grip in self.grips]
        return (
            abs(positions[0][0] - positions[1][0]),
            abs(positions[0][1] - positions[1][1]),
        )

    size = property(__get_size)

    def do_draw(self, cairo_ctx):
        for grip in self.grips:
            if not grip.visible:
                return

        (a_x, a_y) = self.grips[0].position
        (b_x, b_y) = self.grips[1].position
        a_x -= self.canvas.offset[0]
        a_y -= self.canvas.offset[1]
        b_x -= self.canvas.offset[0]
        b_y -= self.canvas.offset[1]

        cairo_ctx.set_source_rgb(self.COLOR[0], self.COLOR[1], self.COLOR[2])
        cairo_ctx.set_line_width(1.0)
        cairo_ctx.rectangle(a_x, a_y, b_x - a_x, b_y - a_y)
        cairo_ctx.stroke()


class ImgGripHandler(GObject.GObject):
    __gsignals__ = {
        'grip-moved': (GObject.SignalFlags.RUN_LAST, None, ()),
        'zoom-changed': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, img, canvas, zoom_widget, default_grips_positions=None):
        GObject.GObject.__init__(self)

        if zoom_widget is None:
            zoom_widget = Gtk.Adjustment(value=1.0, lower=0.01, upper=1.0,
                                         step_increment=0.01,
                                         page_increment=0.10)
        self.zoom_widget = zoom_widget

        self.__visible = False

        self.img = img
        self.img_size = self.img.size
        self.canvas = canvas

        self.img_drawer = PillowImageDrawer((0, 0), img)

        if default_grips_positions is None:
            default_grips_positions = ((0, 0), self.img_size)
        else:
            default_grips_positions = (
                (
                    min(
                        max(0, default_grips_positions[0][0]),
                        self.img_size[0]
                    ),
                    min(
                        max(0, default_grips_positions[0][1]),
                        self.img_size[1]
                    ),
                ),
                (
                    min(
                        max(0, default_grips_positions[1][0]),
                        self.img_size[0]
                    ),
                    min(
                        max(0, default_grips_positions[1][1]),
                        self.img_size[1]
                    ),
                ),
            )
            default_grips_positions = (
                (
                    min(default_grips_positions[0][0],
                        default_grips_positions[1][0]),
                    min(default_grips_positions[0][1],
                        default_grips_positions[1][1]),
                ),
                (
                    max(default_grips_positions[0][0],
                        default_grips_positions[1][0]),
                    max(default_grips_positions[0][1],
                        default_grips_positions[1][1]),
                ),
            )

        self.grips = (
            ImgGrip(default_grips_positions[0], self.img_size),
            ImgGrip(default_grips_positions[1], self.img_size),
        )
        select_rectangle = ImgGripRectangle(self.grips)

        self.selected = None  # the grip being moved

        self.__cursors = {
            'default': Gdk.Cursor.new(Gdk.CursorType.HAND1),
            'visible': Gdk.Cursor.new(Gdk.CursorType.HAND1),
            'on_grip': Gdk.Cursor.new(Gdk.CursorType.TCROSS)
        }

        zoom_widget.connect("value-changed", lambda x:
                            GLib.idle_add(self.__on_zoom_changed))
        canvas.connect("absolute-button-press-event",
                       self.__on_mouse_button_pressed_cb)
        canvas.connect("absolute-motion-notify-event",
                       self.__on_mouse_motion_cb)
        canvas.connect("absolute-button-release-event",
                       self.__on_mouse_button_released_cb)

        self.last_rel_position = (False, 0, 0)
        self.toggle_zoom((0.0, 0.0))

        self.canvas.remove_all_drawers()
        self.canvas.add_drawer(self.img_drawer)
        self.canvas.add_drawer(select_rectangle)
        for grip in self.grips:
            self.canvas.add_drawer(grip)

    def __on_zoom_changed(self):
        self.img_drawer.size = (
            self.img_size[0] * self.scale,
            self.img_size[1] * self.scale,
        )

        for grip in self.grips:
            grip.scale = self.scale

        if self.last_rel_position[0]:
            rel_pos = self.last_rel_position[1:]
            self.last_rel_position = (False, 0, 0)
        else:
            h = self.canvas.get_hadjustment()
            v = self.canvas.get_vadjustment()
            adjs = [h, v]
            rel_pos = []
            for adj in adjs:
                upper = adj.get_upper() - adj.get_page_size()
                lower = adj.get_lower()
                if (upper - lower) <= 0:
                    # XXX(Jflesch): Weird bug ?
                    break
                val = adj.get_value()
                val -= lower
                val /= (upper - lower)
                rel_pos.append(val)
        if len(rel_pos) >= 2:
            GLib.idle_add(self.__replace_scrollbars, rel_pos)

        self.canvas.recompute_size()

        self.emit("zoom-changed")

    def __replace_scrollbars(self, rel_cursor_pos):
        adjustements = [
            (self.canvas.get_hadjustment(), rel_cursor_pos[0]),
            (self.canvas.get_vadjustment(), rel_cursor_pos[1]),
        ]
        for (adjustment, val) in adjustements:
            upper = adjustment.get_upper() - adjustment.get_page_size()
            lower = adjustment.get_lower()
            val = (val * (upper - lower)) + lower
            adjustment.set_value(int(val))

    def __get_scale(self):
        return float(self.zoom_widget.get_value())

    scale = property(__get_scale)

    def toggle_zoom(self, rel_cursor_pos):
        if self.scale != 1.0:
            scale = 1.0
        else:
            scale = min(
                float(self.canvas.visible_size[0]) / self.img_size[0],
                float(self.canvas.visible_size[1]) / self.img_size[1]
            )
        self.last_rel_position = (True, rel_cursor_pos[0], rel_cursor_pos[1])
        self.zoom_widget.set_value(scale)

    def __on_mouse_button_pressed_cb(self, widget, event):
        if not self.visible:
            return
        self.selected = None
        for grip in self.grips:
            if grip.is_on_grip((event.x, event.y)):
                self.selected = grip
                grip.selected = True
                break

    def __move_grip(self, event_pos):
        """
        Move a grip, based on the position
        """
        if not self.selected:
            return None

        new_x = event_pos[0] / self.scale
        new_y = event_pos[1] / self.scale
        self.selected.img_position = (new_x, new_y)

    def __on_mouse_motion_cb(self, widget, event):
        if not self.visible:
            return
        if self.selected:
            self.__move_grip((event.x, event.y))
            is_on_grip = True
            self.img_drawer.redraw()
        else:
            is_on_grip = False
            for grip in self.grips:
                if grip.is_on_grip((event.x, event.y)):
                    grip.hover = True
                    is_on_grip = True
                else:
                    grip.hover = False
            self.img_drawer.redraw()

        if is_on_grip:
            cursor = self.__cursors['on_grip']
        else:
            cursor = self.__cursors['visible']
        self.canvas.get_window().set_cursor(cursor)

    def __on_mouse_button_released_cb(self, widget, event):
        if not self.selected:
            # figure out the cursor position on the image
            (img_w, img_h) = self.img_size
            rel_cursor_pos = (
                float(event.x) / (img_w * self.scale),
                float(event.y) / (img_h * self.scale),
            )
            self.toggle_zoom(rel_cursor_pos)
            self.img_drawer.redraw()
            self.emit('zoom-changed')
            return

        if not self.visible:
            return

        self.selected.selected = False
        self.selected = None
        self.emit('grip-moved')

    def __get_visible(self):
        return self.__visible

    def __set_visible(self, visible):
        self.__visible = visible
        for grip in self.grips:
            grip.visible = visible
        if self.canvas.get_window():
            self.canvas.get_window().set_cursor(self.__cursors['default'])
        self.img_drawer.redraw()

    visible = property(__get_visible, __set_visible)

    def get_coords(self):
        a_x = min(self.grips[0].img_position[0],
                  self.grips[1].img_position[0])
        a_y = min(self.grips[0].img_position[1],
                  self.grips[1].img_position[1])
        b_x = max(self.grips[0].img_position[0],
                  self.grips[1].img_position[0])
        b_y = max(self.grips[0].img_position[1],
                  self.grips[1].img_position[1])
        return ((int(a_x), int(a_y)), (int(b_x), int(b_y)))


GObject.type_register(ImgGripHandler)
