#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
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

import os

import logging

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk

from paperwork_backend.labels import Label
from paperwork.frontend.util import load_uifile
from paperwork.frontend.util.actions import SimpleAction
from paperwork.frontend.util.dialog import ask_confirmation


logger = logging.getLogger(__name__)

DROPPER_BITS = (
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377\377\377\377\377\377\377\377"
    b"\377\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377\377\0\0\0\377"
    b"\0\0\0\377\0\0\0\377\377\377\377\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377"
    b"\377\0\0\0\377\0\0\0\377\0\0\0\377\0\0\0\377\0\0\0\377\377\377\377\377"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377"
    b"\377\377\377\377\377\377\377\377\377\377\377\0\0\0\377\0\0\0\377\0\0"
    b"\0\377\0\0\0\377\0\0\0\377\377\377\377\377\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377\377\0\0\0\377\0\0\0\377\0"
    b"\0\0\377\0\0\0\377\0\0\0\377\0\0\0\377\0\0\0\377\0\0\0\377\377\377\377"
    b"\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\377\377\377\377\0\0\0\377\0\0\0\377\0\0\0\377\0\0\0\377\0\0\0\377\0"
    b"\0\0\377\377\377\377\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377\377\377\0\0\0\377\0\0"
    b"\0\377\0\0\0\377\377\377\377\377\377\377\377\377\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377"
    b"\377\377\377\377\377\377\377\377\377\377\0\0\0\377\0\0\0\377\377\377"
    b"\377\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\377\377\377\377\377\377\377\377\377\377\377\377\377"
    b"\0\0\0\377\377\377\377\377\0\0\0\377\377\377\377\377\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377\377"
    b"\377\377\377\377\377\377\377\377\377\0\0\0\377\0\0\0\0\0\0\0\0\377\377"
    b"\377\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\377\377\377\377\377\377\377\377\377\377\377\377\377\0\0\0"
    b"\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377\377\377\377\377\377\377\377"
    b"\377\377\377\0\0\0\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377\377\377"
    b"\377\377\377\377\377\377\377\377\0\0\0\377\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\377\377\377\377\377\377\377\377\377\377\377\377\377\0\0\0\377\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\377\377\377\377\377\377\377\377\0\0"
    b"\0\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\0\0\0\0\0\0\0\377\0\0\0"
    b"\377\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\377\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
    b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
)
DROPPER_WIDTH = 17
DROPPER_HEIGHT = 17
DROPPER_X_HOT = 2
DROPPER_Y_HOT = 16


class PickColorAction(SimpleAction):
    """
    Hack taken from libgtk3/gtk/deprecated/gtkcolorsel.c
    """
    def __init__(self, label_editor):
        super(PickColorAction, self).__init__("Pick color")
        self.__editor = label_editor
        self.__dropper_grab_widget = None
        self.__grab_time = None
        self.__has_grab = False
        self.__pointer_device = None

    def do(self):
        self._get_screen_color()

    def _make_picker_cursor(self, display):
        if os.name == 'nt':
            return Gdk.Cursor.new_for_display(display, Gdk.CursorType.CIRCLE)

        try:
            cursor = Gdk.Cursor.new_from_name(display, "color-picker")
            if cursor is not None:
                return cursor
        except TypeError:
            pass
        logger.info("Cursor color-picker not found. Falling back on built-in"
                    " color picker")

        try:
            # happens when new_from_name returns NULL at C level
            pixbuf = GdkPixbuf.Pixbuf.new_from_data(
                DROPPER_BITS, GdkPixbuf.Colorspace.RGB, True, 8,
                DROPPER_WIDTH, DROPPER_HEIGHT,
                DROPPER_WIDTH * 4
            )
            cursor = Gdk.Cursor.new_from_pixbuf(display, pixbuf,
                                                DROPPER_X_HOT, DROPPER_Y_HOT)
            if cursor is not None:
                return cursor
        except TypeError as exc:
            logger.exception(exc)

        logger.warning("Failed to load color-picker cursor")
        return None

    def _get_screen_color(self):
        time = Gtk.get_current_event_time()
        screen = self.__editor._pick_button.get_screen()
        display = self.__editor._pick_button.get_display()

        # XXX(JFlesch): Assumption: mouse is used
        pointer_device = Gtk.get_current_event_device()

        if not self.__dropper_grab_widget:
            self.__dropper_grab_widget = Gtk.Window.new(Gtk.WindowType.POPUP)
            self.__dropper_grab_widget.set_screen(screen)
            self.__dropper_grab_widget.resize(1, 1)
            self.__dropper_grab_widget.move(-100, -100)
            self.__dropper_grab_widget.show()
            self.__dropper_grab_widget.add_events(
                Gdk.EventMask.BUTTON_RELEASE_MASK
            )
            toplevel = self.__editor._pick_button.get_toplevel()

            if isinstance(toplevel, Gtk.Window):
                if toplevel.has_group():
                    toplevel.get_group().add_window(self.__dropper_grab_widget)

        window = self.__dropper_grab_widget.get_window()

        picker_cursor = self._make_picker_cursor(display)
        if (pointer_device.grab(
                window,
                Gdk.GrabOwnership.APPLICATION, False,
                Gdk.EventMask.BUTTON_RELEASE_MASK,
                picker_cursor, time) != Gdk.GrabStatus.SUCCESS):
            logger.warning("Pointer device grab failed !")
            return

        Gtk.device_grab_add(self.__dropper_grab_widget, pointer_device, True)

        self.__grab_time = time
        self.__pointer_device = pointer_device
        self.__has_grab = True

        self.__dropper_grab_widget.connect("button-release-event",
                                           self._on_mouse_release)

    def _grab_color_at_pointer(self, screen, device, x, y):
        root_window = screen.get_root_window()

        pixbuf = Gdk.pixbuf_get_from_window(root_window, x, y, 1, 1)
        # XXX(Jflesch): bad shortcut here ...

        pixels = pixbuf.get_pixels()
        rgb = (
            float(pixels[0] * 0x101) / 65535,
            float(pixels[1] * 0x101) / 65535,
            float(pixels[2] * 0x101) / 65535,
        )
        logger.info("Picked color: %s" % str(rgb))
        return rgb

    def _on_mouse_release(self, invisible_widget, event):
        if not self.__has_grab:
            return
        try:
            color = self._grab_color_at_pointer(
                event.get_screen(), event.get_device(),
                event.x_root, event.y_root
            )
            self.__editor._color_chooser.set_rgba(
                Gdk.RGBA(
                    red=color[0],
                    green=color[1],
                    blue=color[2],
                    alpha=1.0
                )
            )
        finally:
            self.__pointer_device.ungrab(self.__grab_time)
            Gtk.device_grab_remove(self.__dropper_grab_widget,
                                    self.__pointer_device)
            self.__has_grab = False
            self.__pointer_device = None


class LabelEditor(object):
    """
    Dialog to create / edit labels
    """

    def __init__(self, label_to_edit=None):
        if label_to_edit is None:
            label_to_edit = Label()
        self.label = label_to_edit

        self.__ok_button = None

    def edit(self, main_window):
        """
        Open the edit dialog, and update the label according to user changes
        """
        widget_tree = load_uifile(
            os.path.join("labeleditor", "labeleditor.glade"))

        dialog = widget_tree.get_object("dialogLabelEditor")
        dialog.set_transient_for(main_window)

        # don't force the window to be centered. Otherwise, user can't use the picker to pick colors
        # from the current document
        dialog.set_position(Gtk.WindowPosition.NONE)

        self.__ok_button = widget_tree.get_object("buttonOk")
        self._pick_button = widget_tree.get_object("buttonPickColor")
        PickColorAction(self).connect([self._pick_button])

        self._color_chooser = widget_tree.get_object("labelColorChooser")
        self._color_chooser.set_rgba(self.label.color)

        name_entry = widget_tree.get_object("entryLabelName")
        name_entry.connect("changed", self.__on_label_entry_changed)
        name_entry.set_text(self.label.name)

        response = dialog.run()

        if (response == Gtk.ResponseType.OK
                and name_entry.get_text().strip() == ""):
            response = Gtk.ResponseType.CANCEL

        if (response == Gtk.ResponseType.OK):
            logger.info("Label validated")
            self.label.name = name_entry.get_text()
            self.label.color = self._color_chooser.get_rgba()
            logger.info("Label after editing: %s" % self.label)
        else:
            logger.info("Label editing canceled")

        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            return "ok"
        else:
            return "canceled"

    def __on_label_entry_changed(self, label_entry):
        txt = label_entry.get_text().strip()
        ok_enabled = True
        ok_enabled = ok_enabled and txt != u""
        ok_enabled = ok_enabled and u"," not in txt
        self.__ok_button.set_sensitive(ok_enabled)
