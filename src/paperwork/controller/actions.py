import gtk

class SimpleAction(object):
    """
    Template for all the actions started by buttons
    """
    def __init__(self, name):
        self.name = name

    def do(self):
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
            elif isinstance(button, gtk.TreeView):
                button.connect("cursor-changed",
                               self.on_treeview_cursor_changed_cb)
            elif isinstance(button, gtk.IconView):
                button.connect("selection-changed",
                               self.on_iconview_selection_changed_cb)
            elif isinstance(button, gtk.ComboBox):
                button.connect("changed", self.on_combobox_changed_cb)
            else:
                assert()
