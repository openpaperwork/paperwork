import os

from ..util import load_uifile
from ..util.actions import SimpleAction


class ActionOpenSummary(SimpleAction):
    """
    Quit
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open summary")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.switch_mainview("summary")


class Summary(object):
    def __init__(self, main_window, config):
        summary_tree = load_uifile(os.path.join("mainwindow", "summary.glade"))
        self.view = summary_tree.get_object("summary_view")
        self.doc_count = summary_tree.get_object("labelPaperCount")
        self.page_count = summary_tree.get_object("labelPageCount")
        self.total_size = summary_tree.get_object("labelTotalSize")
        self._main_window = main_window
        self._config = config

    def refresh(self):
        pass
