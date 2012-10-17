#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
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

import gtk

class SimpleAction(object):
    """
    Template for all the actions started by buttons
    """
    def __init__(self, name):
        self.name = name
        self.__signal_handlers = [
            (gtk.ToolButton, "clicked", self.on_button_clicked_cb, -1),
            (gtk.Button, "clicked", self.on_button_clicked_cb, -1),
            (gtk.MenuItem, "activate", self.on_menuitem_activate_cb, -1),
            (gtk.Editable, "changed", self.on_entry_changed_cb, -1),
            (gtk.Editable, "activate", self.on_entry_activate_cb, -1),
            (gtk.Entry, "icon-press", self.on_icon_press_cb, -1),
            (gtk.TreeView, "cursor-changed",
             self.on_treeview_cursor_changed_cb, -1),
            (gtk.IconView, "selection-changed",
             self.on_iconview_selection_changed_cb, -1),
            (gtk.ComboBox, "changed", self.on_combobox_changed_cb, -1),
            (gtk.CellRenderer, "edited", self.on_cell_edited_cb, -1),
            (gtk.Range, "value-changed", self.on_value_changed_cb, -1),
        ]
        self.enabled = True

    def do(self, **kwargs):
        print "Action: [%s]" % (self.name)

    def __do(self, **kwargs):
        if not self.enabled:
            return
        self.do(**kwargs)

    def on_button_clicked_cb(self, toolbutton):
        self.__do()

    def on_menuitem_activate_cb(self, menuitem):
        self.__do()

    def on_entry_changed_cb(self, entry):
        self.__do()

    def on_entry_activate_cb(self, entry):
        self.__do()

    def on_treeview_cursor_changed_cb(self, treeview):
        self.__do()

    def on_iconview_selection_changed_cb(self, iconview):
        self.__do()

    def on_combobox_changed_cb(self, combobox):
        self.__do()

    def on_cell_edited_cb(self, cellrenderer, path, new_text):
        self.__do(new_text=new_text)

    def on_icon_press_cb(self, entry=None, iconpos=None, event=None):
        self.__do()

    def on_value_changed_cb(self, widget_range=None):
        self.__do()

    def connect(self, buttons):
        for button in buttons:
            assert(button != None)
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
