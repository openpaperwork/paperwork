#   Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2013  Jerome Flesch
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

import PIL.ImageDraw

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject

from paperwork.frontend.util.canvas.drawers import Drawer
from paperwork.frontend.util.canvas.drawers import PillowImageDrawer
from paperwork.frontend.util.img import image2pixbuf


class ImgGrip(Drawer):
    """
    Represents one of the grip that user can move to cut an image.
    """
    layer = Drawer.BOX_LAYER

    GRIP_SIZE = 20
    DEFAULT_COLOR = (0.0, 0.0, 1.0)
    SELECTED_COLOR = (0.0, 1.0, 0.0)

    def __init__(self, position, size, max_position):
        self.position = position
        self.size = size
        self.max_position = max_position
        self.scale = 1.0
        self.selected = False

    def __get_on_screen_pos(self):
        x = int(self.scale * self.position[0])
        y = int(self.scale * self.position[1])
        return (x, y)

    def __get_select_area(self):
        (x, y) = self.__get_on_screen_pos(self.scale)
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
        ((x_min, y_min), (x_max, y_max)) = self.__get_select_area(scale)
        return (x_min <= position[0] and position[0] <= x_max
                and y_min <= position[1] and position[1] <= y_max)

    on_screen_position = property(__get_on_screen_pos)

    def do_draw(self, cairo_ctx, canvas_offset, canvas_size):
        ((a_x, a_y), (b_x, b_y)) = self.__get_select_area(scale)
        a_x -= canvas_offset[0]
        a_y -= canvas_offset[1]
        b_x -= canvas_offset[0]
        b_y -= canvas_offset[1]

        color = {
            False: self.DEFAULT_COLOR,
            True: self.SELECTED_COLOR,
        }[self.selected]

        cairo_ctx.set_source_rgb(color[0], color[1], color[2])
        cairo_ctx.set_line_width(1.0)
        cairo_ctx.rectangle(a_x, a_y, b_x - a_x, b_y - a_y)
        cairo_ctx.stroke()


class ImgGripRectangle(Drawer):
    layer = (Drawer.BOX_LAYER + 1)  # draw below/before the grips itself

    COLOR = (0.0, 0.0, 1.0)

    def __init__(self, size, grips):
        self.size = size
        self.grips = grips

    def do_draw(self, cairo_ctx, canvas_offset, canvas_size):
        (a_x, a_y) = self.grips[0].on_screen_position
        (b_x, b_y) = self.grips[1].on_screen_position
        a_x -= canvas_offset[0]
        a_y -= canvas_offset[1]
        b_x -= canvas_offset[0]
        b_y -= canvas_offset[1]

        cairo_ctx.set_source_rgb(self.COLOR[0], self.COLOR[1], self.COLOR[2])
        cairo_ctx.set_line_width(1.0)
        cairo_ctx.rectangle(a_x, a_y, b_x - a_x, b_y - a_y)
        cairo_ctx.stroke()


class ImgGripHandler(GObject.GObject):
    __gsignals__ = {
        'grip-moved': (GObject.SignalFlags.RUN_LAST, None, ())
    }

    def __init__(self, img, canvas):
        GObject.GObject.__init__(self)

        self.__visible = False

        self.img = img
        self.scale = 1.0
        self.img_size = self.img.size
        self.canvas = canvas

        self.img_drawer = PillowImageDrawer((0, 0), img)
        self.grips = (
            ImgGrip((0, 0), self.img_size),
            ImgGrip(self.img_size, self.img_size),
        )
        select_rectangle = ImgGripRectangle(self.img_size, self.grips)

        self.selected = None  # the grip being moved

        self.__cursors = {
            'default': Gdk.Cursor.new(Gdk.CursorType.HAND1),
            'visible': Gdk.Cursor.new(Gdk.CursorType.HAND1),
            'on_grip': Gdk.Cursor.new(Gdk.CursorType.TCROSS)
        }

        canvas.connect("absolute-button-press-event",
                       self.__on_mouse_button_pressed_cb)
        canvas.connect("absolute-motion-notify-event",
                       self.__on_mouse_motion_cb)
        canvas.connect("absolute-button-release-event",
                       self.__on_mouse_button_released_cb)

        toggle_zoom()

        self.canvas.remove_all_drawers()
        self.canvas.add_drawer(self.img_drawer)
        self.canvas.add_drawer(select_rectangle)
        for grip in self.grips:
            self.canvas.add_drawer(grip)

    def toggle_zoom(self, relative_cursor_position=None):
        # TODO
        pass

    def __on_mouse_button_pressed_cb(self, widget, event):
        (mouse_x, mouse_y) = event.get_coords()

        self.selected = None
        for grip in self.grips:
            if grip.is_on_grip((mouse_x, mouse_y)):
                self.selected = grip
                break

    def __on_mouse_motion_cb(self, widget, event):
        (mouse_x, mouse_y) = event.get_coords()

        if self.selected:
            is_on_grip = True
        else:
            is_on_grip = False
            for grip in self.grips:
                if grip.is_on_grip((mouse_x, mouse_y)):
                    is_on_grip = True
                    break

        if is_on_grip:
            cursor = self.__cursors['on_grip']
        else:
            cursor = self.__cursors['visible']
        self.img_widget.get_window().set_cursor(cursor)

    def __move_grip(self, event_pos):
        """
        Move a grip, based on the position
        """
        (mouse_x, mouse_y) = event_pos

        if not self.selected:
            return None

        new_x = mouse_x / self.scale
        new_y = mouse_y / self.scale
        self.selected.position = (new_x, new_y)

    def __on_mouse_button_released_cb(self, widget, event):
        if self.selected:
            self.__move_grip(event.get_coords())
            self.selected = None
        else:
            # figure out the cursor position on the image
            (mouse_x, mouse_y) = event.get_coords()
            (img_w, img_h) = self.img_size
            rel_cursor_pos = (
                float(mouse_x) / img_w,
                float(mouse_y) / img_h
            )
            self.toggle_zoom(rel_cursor_pos)
        self.canvas.redraw()
        self.emit('grip-moved')

    def __get_visible(self):
        return self.__visible

    def __set_visible(self, visible):
        self.__visible = visible
        self.img_widget.get_window().set_cursor(self.__cursors['default'])
        self.canvas.redraw()

    visible = property(__get_visible, __set_visible)

    def get_coords(self):
        return ((int(self.grips[0].position[0]),
                 int(self.grips[0].position[1])),
                (int(self.grips[1].position[0]),
                 int(self.grips[1].position[1])))


GObject.type_register(ImgGripHandler)
