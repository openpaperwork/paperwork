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


def connect_buttons(buttons, actions):
    for button in buttons:
        assert(button != None)
        for action in actions:
            if isinstance(button, gtk.ToolButton):
                button.connect("clicked", action.button_clicked)
            elif isinstance(button, gtk.Button):
                button.connect("clicked", action.button_clicked)
            elif isinstance(button, gtk.MenuItem):
                button.connect("activate", action.menuitem_activate)
            else:
                assert()

def do_actions(actions, **kwargs):
    for action in actions:
        action.do(**kwargs)
