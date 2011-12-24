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
        self.__widget_tree = load_uifile("aboutdialog.glade")
        self.__aboutdialog = self.__widget_tree.get_object("aboutdialog")
        self.__aboutdialog.set_transient_for(main_window)
        assert(self.__aboutdialog)
        self.__connect_signals()

    def __connect_signals(self):
        """
        Connect gtk widget signals to methods
        """
        self.__aboutdialog.connect("destroy", self.destroy_cb)
        self.__aboutdialog.connect("response", self.destroy_cb)
        self.__aboutdialog.connect("close", self.destroy_cb)

    def show(self):
        """
        Make the about dialog appears
        """
        self.__aboutdialog.set_visible(True)

    def destroy_cb(self, widget=None, response=None):
        """
        Close and destroy the about dialog window
        """
        self.__widget_tree.get_object("aboutdialog").destroy()
