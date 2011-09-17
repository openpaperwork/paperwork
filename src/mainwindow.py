import gtk

from util import load_uifile

from aboutdialog import AboutDialog
from config import DtGrepConfig
from docsearch import DocSearch
from searchwindow import SearchWindow
from settingswindow import SettingsWindow

class MainWindow:
    def __init__(self, config):
        self.config = config
        self.wTree = load_uifile("dtgrep.glade")
        self.mainWindow = self.wTree.get_object("mainWindow")
        assert(self.mainWindow)
        self.connect_signals()
        self.mainWindow.set_visible(True)

    def open_search_window(self, objsrc):
        dsearch = DocSearch(self.config.workdir)
        dsearch.index() # TODO: callback -> progress bar
        SearchWindow(dsearch)

    def connect_signals(self):
        self.mainWindow.connect("destroy", lambda x: self.destroy())
        self.wTree.get_object("toolbuttonQuit").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("menuitemQuit").connect("activate", lambda x: self.destroy())

        self.wTree.get_object("menuitemAbout").connect("activate", lambda x: AboutDialog())

        self.wTree.get_object("menuitemSettings").connect("activate", lambda x: SettingsWindow(self.config))

        self.wTree.get_object("toolbuttonSearch").connect("clicked", self.open_search_window)
        self.wTree.get_object("menuitemSearch").connect("activate", self.open_search_window)

    def destroy(self):
        self.wTree.get_object("mainWindow").destroy()
        gtk.main_quit()

