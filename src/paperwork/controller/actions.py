import gtk

class SimpleAction(object):
    """
    Template for all the actions started by buttons
    """
    def __init__(self, name):
        self.name = name

    def do(self):
        print "Action: %s" % (self.name)

    def button_clicked(self, toolbutton):
        self.do()

    def menuitem_activate(self, menuitem):
        self.do()

    def entry_changed(self, entry):
        self.do()

    def entry_activate(self, entry):
        self.do()

    def treeview_cursor_changed(self, treeview):
        self.do()

    def iconview_selection_changed(self, iconview):
        self.do()

    def combobox_changed(self, combobox):
        self.do()

    def connect(self, buttons):
        for button in buttons:
            assert(button != None)
            if isinstance(button, gtk.ToolButton):
                button.connect("clicked", self.button_clicked)
            elif isinstance(button, gtk.Button):
                button.connect("clicked", self.button_clicked)
            elif isinstance(button, gtk.MenuItem):
                button.connect("activate", self.menuitem_activate)
            elif isinstance(button, gtk.Editable):
                button.connect("changed", self.entry_changed)
                button.connect("activate", self.entry_activate)
            elif isinstance(button, gtk.TreeView):
                button.connect("cursor-changed",
                               self.treeview_cursor_changed)
            elif isinstance(button, gtk.IconView):
                button.connect("selection-changed",
                               self.iconview_selection_changed)
            elif isinstance(button, gtk.ComboBox):
                button.connect("changed", self.combobox_changed)
            else:
                assert()
