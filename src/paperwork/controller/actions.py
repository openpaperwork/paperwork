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

    def treeview_cursor_changed(self, treeview):
        self.do()


def connect_buttons(buttons, action):
    for button in buttons:
        assert(button != None)
        if isinstance(button, gtk.ToolButton):
            button.connect("clicked", action.button_clicked)
        elif isinstance(button, gtk.Button):
            button.connect("clicked", action.button_clicked)
        elif isinstance(button, gtk.MenuItem):
            button.connect("activate", action.menuitem_activate)
        elif isinstance(button, gtk.Editable):
            button.connect("changed", action.entry_changed)
        elif isinstance(button, gtk.TreeView):
            button.connect("cursor-changed",
                           action.treeview_cursor_changed)
        else:
            assert()
