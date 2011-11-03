"""
Contains the code relative to the about dialog (the one you get when you click
on Help->About)
"""

from util import load_uifile


class AboutDialog(object):
    """
    Dialog that appears when you click Help->About.

    By default, this dialog won't be visible. You have to call
    AboutDialog.show().
    """

    def __init__(self, main_window):
        self.widget_tree = load_uifile("aboutdialog.glade")
        self.aboutdialog = self.widget_tree.get_object("aboutdialog")
        self.aboutdialog.set_transient_for(main_window)
        assert(self.aboutdialog)
        self.__connect_signals()

    def __connect_signals(self):
        """
        Connect gtk widget signals to methods
        """
        self.aboutdialog.connect("destroy", lambda x: self.destroy())
        self.aboutdialog.connect("response", lambda x, y: self.destroy())
        self.aboutdialog.connect("close", lambda x: self.destroy())

    def show(self):
        """
        Make the about dialog appears
        """
        self.aboutdialog.set_visible(True)

    def destroy(self):
        """
        Close and destroy the about dialog window
        """
        self.widget_tree.get_object("aboutdialog").destroy()
