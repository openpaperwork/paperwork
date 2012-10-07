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

    def do(self, **kwargs):
        print "Action: [%s]" % (self.name)

    def on_button_clicked_cb(self, toolbutton):
        self.do()

    def on_menuitem_activate_cb(self, menuitem):
        self.do()

    def on_entry_changed_cb(self, entry):
        self.do()

    def on_entry_activate_cb(self, entry):
        self.do()

    def on_treeview_cursor_changed_cb(self, treeview):
        self.do()

    def on_iconview_selection_changed_cb(self, iconview):
        self.do()

    def on_combobox_changed_cb(self, combobox):
        self.do()

    def on_cell_edited_cb(self, cellrenderer, path, new_text):
        self.do(new_text=new_text)

    def on_icon_press_cb(self, entry=None, iconpos=None, event=None):
        self.do()

    def on_value_changed_cb(self, widget_range=None):
        self.do()

    def connect(self, buttons):
        for button in buttons:
            assert(button != None)
            if isinstance(button, gtk.ToolButton):
                button.connect("clicked", self.on_button_clicked_cb)
            elif isinstance(button, gtk.Button):
                button.connect("clicked", self.on_button_clicked_cb)
            elif isinstance(button, gtk.MenuItem):
                button.connect("activate", self.on_menuitem_activate_cb)
            elif isinstance(button, gtk.Editable):
                button.connect("changed", self.on_entry_changed_cb)
                button.connect("activate", self.on_entry_activate_cb)
                if isinstance(button, gtk.Entry):
                    button.connect("icon-press", self.on_icon_press_cb)
            elif isinstance(button, gtk.TreeView):
                button.connect("cursor-changed",
                               self.on_treeview_cursor_changed_cb)
            elif isinstance(button, gtk.IconView):
                button.connect("selection-changed",
                               self.on_iconview_selection_changed_cb)
            elif isinstance(button, gtk.ComboBox):
                button.connect("changed", self.on_combobox_changed_cb)
            elif isinstance(button, gtk.CellRenderer):
                button.connect("edited", self.on_cell_edited_cb)
            elif isinstance(button, gtk.Range):
                button.connect("value-changed", self.on_value_changed_cb)
            else:
                assert()
