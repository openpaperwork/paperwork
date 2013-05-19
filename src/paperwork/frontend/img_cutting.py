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
from gi.repository import GObject

from paperwork.util import image2pixbuf


class ImgGrip(object):
    """
    Represents one of the grip that user can move to cut an image.
    """
    GRIP_SIZE = 20
    COLOR = (0x00, 0x00, 0xFF)

    def __init__(self, pos_x, pos_y):
        self.position = (int(pos_x), int(pos_y))

    def draw(self, img, imgdraw, ratio):
        """
        Draw the grip on the image

        Arguments:
            imgdraw --- drawing area
            ratio --- Scale at which the image is represented
        """
        bbox = img.getbbox()
        img_x = bbox[2] / ratio
        img_y = bbox[3] / ratio
        (pos_x, pos_y) = self.position
        # fix our position in case we are out the image
        if pos_x < 0:
            pos_x = 0
        if pos_x >= img_x:
            pos_x = img_x - 1
        if pos_y < 0:
            pos_y = 0
        if pos_y >= img_y:
            pos_y = img_y
        self.position = (pos_x, pos_y)
        pos_x = int(ratio * pos_x)
        pos_y = int(ratio * pos_y)
        imgdraw.rectangle(((pos_x - self.GRIP_SIZE, pos_y - self.GRIP_SIZE),
                           (pos_x + self.GRIP_SIZE, pos_y + self.GRIP_SIZE)),
                          outline=self.COLOR)

    def is_on_grip(self, position, ratio):
        """
        Indicates if position is on the grip

        Arguments:
            position --- tuple (int, int)
            ratio --- Scale at which the image is represented

        Returns:
            True or False
        """
        x_min = int(ratio * self.position[0]) - self.GRIP_SIZE
        y_min = int(ratio * self.position[1]) - self.GRIP_SIZE
        x_max = int(ratio * self.position[0]) + self.GRIP_SIZE
        y_max = int(ratio * self.position[1]) + self.GRIP_SIZE
        return (x_min <= position[0] and position[0] <= x_max
                and y_min <= position[1] and position[1] <= y_max)


class ImgGripHandler(GObject.GObject):
    __gsignals__ = {
        'grip-moved': (GObject.SignalFlags.RUN_LAST, None, ())
    }

    def __init__(self, imgs, img_scrolledwindow, img_eventbox, img_widget):
        """
        Arguments:
            imgs --- [(factor, PIL img), (factor, PIL img), ...]
            img_eventbox --- Image area eventbox
            img_widget --- Widget displaying the image
        """
        GObject.GObject.__init__(self)
        self.__visible = False

        self.imgs = imgs
        self.img_scrolledwindow = img_scrolledwindow
        self.img_eventbox = img_eventbox
        self.img_widget = img_widget

        self.img_widget.set_alignment(0.0, 0.0)

        bbox = imgs[0][1].getbbox()
        factor = imgs[0][0]
        self.__grips = (
            ImgGrip(0, 0),
            ImgGrip(bbox[2] / factor, bbox[3] / factor))
        self.selected = None  # the grip being moved

        self.__cursors = {
            'default': Gdk.Cursor.new(Gdk.CursorType.HAND1),
            'visible': Gdk.Cursor.new(Gdk.CursorType.HAND1),
            'on_grip': Gdk.Cursor.new(Gdk.CursorType.TCROSS)
        }

        img_eventbox.connect("button-press-event",
                             self.__on_mouse_button_pressed_cb)
        img_eventbox.connect("motion-notify-event",
                             self.__on_mouse_motion_cb)
        img_eventbox.connect("button-release-event",
                             self.__on_mouse_button_released_cb)
        img_eventbox.add_events(Gdk.EventMask.POINTER_MOTION_MASK)

        img_widget.connect("size-allocate",
                           lambda widget, size:
                           GObject.idle_add(self.__on_size_allocate_cb,
                                            widget, size))
        self.__last_cursor_pos = None  # relative to the image size

        self.redraw()

    def __on_mouse_button_pressed_cb(self, widget, event):
        if not self.__visible:
            return

        (mouse_x, mouse_y) = event.get_coords()
        factor = self.imgs[0][0]

        self.selected = None
        for grip in self.__grips:
            if grip.is_on_grip((mouse_x, mouse_y), factor):
                self.selected = grip
                break

    def __on_mouse_motion_cb(self, widget, event):
        if not self.__visible:
            return

        (mouse_x, mouse_y) = event.get_coords()
        factor = self.imgs[0][0]

        if self.selected:
            is_on_grip = True
        else:
            is_on_grip = False
            for grip in self.__grips:
                if grip.is_on_grip((mouse_x, mouse_y), factor):
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
        (factor, img) = self.imgs[0]

        if not self.selected:
            return None

        new_x = mouse_x / factor
        new_y = mouse_y / factor
        self.selected.position = (new_x, new_y)

    def __on_mouse_button_released_cb(self, widget, event):
        if self.selected:
            if not self.__visible:
                return
            self.__move_grip(event.get_coords())
            self.selected = None
        else:
            # figure out the cursor position on the image
            (mouse_x, mouse_y) = event.get_coords()
            img = self.imgs[0][1]
            bbox = img.getbbox()
            img_w = bbox[2]
            img_h = bbox[3]
            self.__last_cursor_pos = (
                float(mouse_x) / img_w,
                float(mouse_y) / img_h
            )

            # switch image
            img = self.imgs.pop()
            self.imgs.insert(0, img)
        GObject.idle_add(self.redraw)
        self.emit('grip-moved')

    def __on_size_allocate_cb(self, viewport, new_size):
        if self.__last_cursor_pos is None:
            return
        (x, y) = self.__last_cursor_pos
        self.__last_cursor_pos = None
        adjustements = [
            (self.img_scrolledwindow.get_hadjustment(), x),
            (self.img_scrolledwindow.get_vadjustment(), y),
        ]
        for (adjustment, val) in adjustements:
            upper = adjustment.get_upper() - adjustment.get_page_size()
            lower = adjustment.get_lower()
            val = (val * (upper - lower) + lower)
            adjustment.set_value(val)

    def __draw_grips(self, img, imgdraw, factor):
        for grip in self.__grips:
            grip.draw(img, imgdraw, factor)
        a = (int(factor * self.__grips[0].position[0]),
             int(factor * self.__grips[0].position[1]))
        b = (int(factor * self.__grips[1].position[0]),
             int(factor * self.__grips[1].position[1]))
        imgdraw.rectangle((a, b), outline=ImgGrip.COLOR)

    def redraw(self):
        (factor, img) = self.imgs[0]
        if self.__visible:
            img = img.copy()
            self.__draw_grips(img, PIL.ImageDraw.Draw(img), factor)
        img = image2pixbuf(img)
        self.img_widget.set_from_pixbuf(img)

    def __get_visible(self):
        return self.__visible

    def __set_visible(self, visible):
        self.__visible = visible
        self.img_widget.get_window().set_cursor(self.__cursors['default'])
        self.redraw()

    visible = property(__get_visible, __set_visible)

    def get_coords(self):
        return ((int(self.__grips[0].position[0]),
                 int(self.__grips[0].position[1])),
                (int(self.__grips[1].position[0]),
                 int(self.__grips[1].position[1])))


GObject.type_register(ImgGripHandler)
