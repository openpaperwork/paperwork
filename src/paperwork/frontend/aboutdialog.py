"""
Contains the code relative to the about dialog (the one you get when you click
on Help->About)
"""

from paperwork.util import load_uifile


class AboutDialog(object):
    """
    Dialog that appears when you click Help->About.

    By default, this dialog won't be visible. You have to call
    AboutDialog.show().
    """

    def __init__(self, main_window):
        self.__widget_tree = load_uifile("aboutdialog.glade")

        self.__dialog = self.__widget_tree.get_object("aboutdialog")
        assert(self.__dialog)
        self.__dialog.set_transient_for(main_window)

        self.__dialog.connect("response", lambda x, y: x.destroy())

    def show(self):
        """
        Make the about dialog appears
        """
        self.__dialog.set_visible(True)
