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

import logging

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject

from paperwork.frontend.util.canvas.drawers import Drawer


logger = logging.getLogger(__name__)


class ImgGrip(Drawer):
    """
    Represents one of the grip that user can move to cut an image.
    """

    layer = Drawer.BOX_LAYER

    GRIP_SIZE = 40
    DEFAULT_COLOR = (0.0, 0.25, 1.0)
    HOVER_COLOR = (0.0, 1.0, 0.0)
    SELECTED_COLOR = (1.0, 0.0, 0.0)

    def __init__(self, handler, position):
        super(ImgGrip, self).__init__()
        self._img_position = position  # position relative to the image
        self.size = (0, 0)
        self.selected = False
        self.hover = False
        self.visible = True
        self.handler = handler

    def __get_img_position(self):
        return self._img_position

    def __set_img_position(self, position):
        self._img_position = (
            min(max(0, position[0]), self.max_position[0]),
            min(max(0, position[1]), self.max_position[1]),
        )

    img_position = property(__get_img_position, __set_img_position)

    def __get_max_position(self):
        return self.handler.img_size

    max_position = property(__get_max_position)

    def __get_on_canvas_pos(self):
        drawer_position = self.handler.img_drawer.position
        x = int(self._img_position[0] * self.handler.scale) + drawer_position[0]
        y = int(self._img_position[1] * self.handler.scale) + drawer_position[1]
        return (x, y)

    def __set_on_canvas_pos(self, position):
        drawer_position = self.handler.img_drawer.position
        position = (
            (position[0] - drawer_position[0]) / self.handler.scale,
            (position[1] - drawer_position[1]) / self.handler.scale
        )
        self.__set_img_position(position)

    position = property(__get_on_canvas_pos, __set_on_canvas_pos)

    def __get_select_area(self, pos):
        (x, y) = self._img_position
        x *= self.handler.scale
        y *= self.handler.scale
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
        ((x_min, y_min), (x_max, y_max)) = \
            self.__get_select_area(self.position)
        return (x_min <= position[0] and position[0] <= x_max and
                y_min <= position[1] and position[1] <= y_max)

    def do_draw(self, cairo_ctx):
        if not self.visible:
            return
        drawer_position = self.handler.img_drawer.position
        ((a_x, a_y), (b_x, b_y)) = \
            self.__get_select_area(self.__get_on_canvas_pos())
        a_x += drawer_position[0]
        a_y += drawer_position[1]
        b_x += drawer_position[0]
        b_y += drawer_position[1]

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

    COLOR = (0.0, 0.25, 1.0)

    def __init__(self, grips):
        super(ImgGripRectangle, self).__init__()
        self.grips = grips

    def __get_size(self):
        positions = [grip.position for grip in self.grips]
        return (
            abs(positions[0][0] - positions[1][0]),
            abs(positions[0][1] - positions[1][1]),
        )

    size = property(__get_size)

    def __get_position(self):
        return (min(self.grips[0].position[0],
                    self.grips[1].position[0]),
                min(self.grips[0].position[1],
                    self.grips[1].position[1]))

    def __set_position(self, _):
        # No op
        pass

    position = property(__get_position, __set_position)

    def do_draw(self, cairo_ctx):
        visible = False
        for grip in self.grips:
            if grip.visible:
                visible = True
                break
        if not visible:
            return

        (a_x, a_y) = self.grips[0].position
        (b_x, b_y) = self.grips[1].position

        cairo_ctx.set_source_rgb(self.COLOR[0], self.COLOR[1], self.COLOR[2])
        cairo_ctx.set_line_width(1.0)
        cairo_ctx.rectangle(a_x, a_y, b_x - a_x, b_y - a_y)
        cairo_ctx.stroke()


class ImgGripHandler(GObject.GObject, Drawer):
    __gsignals__ = {
        'grip-moved': (GObject.SignalFlags.RUN_LAST, None, ()),
        'zoom-changed': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    layer = (Drawer.BOX_LAYER + 1)  # draw below/before the grips itself

    def __init__(self, img_drawer, img_size, zoom_widget=None,
                 default_grips_positions=None, canvas=None):
        """
        Arguments:
            img --- can be Pillow image (will be displayed), or just a tuple
                being the size of the image
        """
        assert(img_drawer)

        super(ImgGripHandler, self).__init__()

        self.canvas = canvas
        self.zoom_widget = zoom_widget

        self.__visible = False

        self.img_size = img_size
        self.img_drawer = img_drawer

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
            ImgGrip(self, default_grips_positions[0]),
            ImgGrip(self, default_grips_positions[1]),
        )
        self.select_rectangle = ImgGripRectangle(self.grips)

        self.selected = None  # the grip being moved

        self.__cursors = {
            'default': Gdk.Cursor.new(Gdk.CursorType.HAND1),
            'visible': Gdk.Cursor.new(Gdk.CursorType.HAND1),
            'on_grip': Gdk.Cursor.new(Gdk.CursorType.TCROSS)
        }

        if zoom_widget:
            zoom_widget.connect("value-changed", lambda x:
                                GLib.idle_add(self.__on_zoom_changed))
        self.last_rel_position = (False, 0, 0)
        if zoom_widget:
            self.toggle_zoom((0.0, 0.0))

        self.drawers = []
        self.drawers.append(self.select_rectangle)
        for grip in self.grips:
            self.drawers.append(grip)

    def set_canvas(self, canvas):
        super(ImgGripHandler, self).set_canvas(canvas)
        for drawer in self.drawers:
            drawer.set_canvas(canvas)
        canvas.connect(self, "absolute-button-press-event",
                       self.__on_mouse_button_pressed_cb)
        canvas.connect(self, "absolute-motion-notify-event",
                       self.__on_mouse_motion_cb)
        canvas.connect(self, "absolute-button-release-event",
                       self.__on_mouse_button_released_cb)

    def _set_size(self, _):
        # no op
        pass

    def _get_size(self):
        return (
            self.img_drawer.size[0] + ImgGrip.GRIP_SIZE,
            self.img_drawer.size[1] + ImgGrip.GRIP_SIZE,
        )

    size = property(_get_size, _set_size)

    def _get_position(self):
        return (
            self.img_drawer.position[0] - ImgGrip.GRIP_SIZE,
            self.img_drawer.position[1] - ImgGrip.GRIP_SIZE,
        )

    def _set_position(self, _):
        # no op
        return

    position = property(_get_position, _set_position)

    def do_draw(self, cairo_ctx):
        for drawer in self.drawers:
            drawer.do_draw(cairo_ctx)

    def on_tick(self):
        for drawer in self.drawers:
            drawer.on_tick()

    def destroy(self):
        pass

    def __on_zoom_changed(self):
        assert(self.zoom_widget)
        scale = self.zoom_widget.get_value()
        self.img_drawer.size = (
            self.img_size[0] * scale,
            self.img_size[1] * scale,
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

        self.canvas.recompute_size(upd_scrollbar_values=False)

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
        return self.img_drawer.size[0] / self.img_size[0]

    scale = property(__get_scale)

    def toggle_zoom(self, rel_cursor_pos):
        assert(self.zoom_widget)
        if self.scale != 1.0 or self.canvas is None:
            scale = 1.0
        else:
            scale = min(
                float(self.canvas.visible_size[0]) / self.img_size[0],
                float(self.canvas.visible_size[1]) / self.img_size[1]
            )
        self.img_drawer.size = (
            self.img_size[0] * scale,
            self.img_size[1] * scale,
        )
        self.last_rel_position = (True, rel_cursor_pos[0], rel_cursor_pos[1])
        self.zoom_widget.set_value(scale)

    def __on_mouse_button_pressed_cb(self, widget, event):
        if not self.visible:
            return

        event_x = event.x - self.img_drawer.position[0]
        event_y = event.y - self.img_drawer.position[1]

        self.selected = None
        for grip in self.grips:
            if grip.is_on_grip((event_x, event_y)):
                self.selected = grip
                grip.selected = True
                break

    def __move_grip(self, event_pos):
        """
        Move a grip, based on the position
        """
        if not self.selected:
            return None

        self.selected.position = (event_pos[0], event_pos[1])

    def __on_mouse_motion_cb(self, widget, event):
        if not self.visible:
            return

        event_x = event.x - self.img_drawer.position[0]
        event_y = event.y - self.img_drawer.position[1]

        if self.selected:
            self.__move_grip((event.x, event.y))
            is_on_grip = True
            self.img_drawer.redraw(ImgGrip.GRIP_SIZE / 2)
        else:
            is_on_grip = False
            for grip in self.grips:
                if grip.is_on_grip((event_x, event_y)):
                    grip.hover = True
                    is_on_grip = True
                else:
                    grip.hover = False
            self.img_drawer.redraw(ImgGrip.GRIP_SIZE / 2)

        if is_on_grip:
            cursor = self.__cursors['on_grip']
        else:
            cursor = self.__cursors['visible']
        self.canvas.get_window().set_cursor(cursor)

    def __on_mouse_button_released_cb(self, widget, event):
        event_x = event.x - self.img_drawer.position[0]
        event_y = event.y - self.img_drawer.position[1]

        if not self.selected:
            if not self.zoom_widget:
                return
            # figure out the cursor position on the image
            (img_w, img_h) = self.img_size
            rel_cursor_pos = (
                float(event_x) / (img_w / self.scale),
                float(event_y) / (img_h / self.scale),
            )
            self.toggle_zoom(rel_cursor_pos)
            self.img_drawer.redraw(ImgGrip.GRIP_SIZE / 2)
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
        self.img_drawer.redraw(ImgGrip.GRIP_SIZE / 2)

    visible = property(__get_visible, __set_visible)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

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

    def rotate_coords(self, angle):
        # The drawer may already be rotated while the image is not.
        # We have to take that into account
        (size_x, size_y) = self.img_size

        assert(angle % 90 == 0)
        assert(angle >= 0 and angle < 360)
        if angle == 0:
            return

        a_x = self.grips[0].img_position[0]
        a_y = self.grips[0].img_position[1]
        b_x = self.grips[1].img_position[0]
        b_y = self.grips[1].img_position[1]

        logger.info(
            "Rotating chopping coords {} by {} degrees (img size: {})".format(
                (a_x, a_y, b_x, b_y),
                angle, (size_x, size_y)
            )
        )

        if angle == 90:
            # beware: img_size has already been changed, but not our coords
            (a_x, a_y, b_x, b_y) = (size_x - b_y, a_x, size_x - a_y, b_x)
        elif angle == 180:
            (a_x, a_y, b_x, b_y) = (
                size_x - b_x, size_y - b_y, size_x - a_x, size_y - a_y
            )
        elif angle == 270:
            # beware: img_size has already been changed, but not our coords
            (a_x, a_y, b_x, b_y) = (a_y, size_y - b_x, b_y, size_y - a_x)

        logger.info(
            "Rotation result: {} (img size: {})".format(
                (a_x, a_y, b_x, b_y), (size_x, size_y)
            )
        )

        self.grips[0].img_position = (a_x, a_y)
        self.grips[1].img_position = (b_x, b_y)


GObject.type_register(ImgGripHandler)
