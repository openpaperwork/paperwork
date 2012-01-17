"""
Dialog to scan many pages and document at once
"""

from paperwork.util import load_uifile


class MultiscanDialog(object):
    def __init__(self, mainwindow, config, device):
        self.__mainwindow = mainwindow
        self.__config = config
        self.__device = device
        self.__widget_tree = load_uifile("multiscan.glade")

        self.__multiscandialog = \
                self.__widget_tree.get_object("dialogMultiscan")

        # TODO ..

        self.connect_signals()

        self.__multiscandialog.set_visible(True)


    def connect_signals(self):
        pass
