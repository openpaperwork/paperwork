#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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

from gi.repository import Gio
from gi.repository import Gtk

logger = logging.getLogger(__name__)


class SimpleAction(object):

    """
    Template for all the actions started by buttons
    """

    def __init__(self, name):
        self.enabled = True
        self.name = name
        self.__signal_handlers = [
            (Gtk.ToolButton, "clicked", self.on_button_clicked_cb, -1),
            (Gtk.Button, "clicked", self.on_button_clicked_cb, -1),
            (Gtk.MenuItem, "activate", self.on_menuitem_activate_cb, -1),
            (Gtk.Editable, "changed", self.on_entry_changed_cb, -1),
            (Gtk.Editable, "activate", self.on_entry_activate_cb, -1),
            (Gtk.Entry, "icon-press", self.on_icon_press_cb, -1),
            (Gtk.TreeView, "cursor-changed",
             self.on_treeview_cursor_changed_cb, -1),
            (Gtk.IconView, "selection-changed",
             self.on_iconview_selection_changed_cb, -1),
            (Gtk.ComboBox, "changed", self.on_combobox_changed_cb, -1),
            (Gtk.CellRenderer, "edited", self.on_cell_edited_cb, -1),
            (Gtk.Range, "value-changed", self.on_value_changed_cb, -1),
            (Gio.Action, "activate", self.on_action_activated_cb, -1),
            (Gtk.ListBox, "row-activated", self.on_row_activated_cb, -1),
            (Gtk.Calendar, "day-selected-double-click",
             self.on_day_selected_cb, -1),
            (Gtk.Dialog, "delete-event", self.on_dialog_closed_cb, -1),
            (Gtk.Switch, "notify::active", self.on_switch_activated_cb, -1),
            (Gtk.Adjustment, "value-changed",
             self.on_adjustment_value_changed_cb, -1)
        ]

    def do(self, **kwargs):
        logger.info("Action: [%s]" % (self.name))

    def __do(self, **kwargs):
        if not self.enabled:
            return
        return self.do(**kwargs)

    def on_button_clicked_cb(self, toolbutton):
        return self.__do()

    def on_menuitem_activate_cb(self, menuitem):
        return self.__do()

    def on_entry_changed_cb(self, entry):
        return self.__do()

    def on_entry_activate_cb(self, entry):
        return self.__do()

    def on_treeview_cursor_changed_cb(self, treeview):
        return self.__do()

    def on_iconview_selection_changed_cb(self, iconview):
        return self.__do()

    def on_combobox_changed_cb(self, combobox):
        return self.__do()

    def on_cell_edited_cb(self, cellrenderer, path, new_text):
        return self.__do(new_text=new_text)

    def on_icon_press_cb(self, entry=None, iconpos=None, event=None):
        return self.__do()

    def on_value_changed_cb(self, widget_range=None):
        return self.__do()

    def on_action_activated_cb(self, action, parameter):
        return self.__do()

    def on_row_activated_cb(self, *args, **kwargs):
        return self.__do()

    def on_day_selected_cb(self, calendar):
        return self.__do()

    def on_dialog_closed_cb(self, dialog, config):
        return self.__do()

    def on_switch_activated_cb(self, switch, val):
        return self.__do()

    def on_adjustment_value_changed_cb(self, adj):
        return self.__do()

    def connect(self, buttons):
        for button in buttons:
            assert(button is not None)
            handled = False
            for handler_idx in range(0, len(self.__signal_handlers)):
                (obj_class, signal, handler, handler_id) = \
                    self.__signal_handlers[handler_idx]
                if isinstance(button, obj_class):
                    handler_id = button.connect(signal, handler)
                    handled = True
                self.__signal_handlers[handler_idx] = \
                    (obj_class, signal, handler, handler_id)
            assert(handled)
