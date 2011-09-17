import gtk

from util import gtk_refresh
from util import load_uifile

from aboutdialog import AboutDialog
from config import DtGrepConfig
from docsearch import DocSearch
from searchwindow import SearchWindow
from settingswindow import SettingsWindow

class MainWindow:
    def __init__(self, config):
        self.config = config
        self.wTree = load_uifile("mainwindow.glade")
        self.mainWindow = self.wTree.get_object("mainWindow")
        self.progressBar = self.wTree.get_object("progressbarMainWin")
        assert(self.mainWindow)
        self._connect_signals()
        self.mainWindow.set_visible(True)

    def _docsearch_callback(self, step, progression, total, document=None):
        self.progressBar.set_fraction(float(progression) / total)
        if step == DocSearch.INDEX_STEP_READING:
            self.progressBar.set_text("Reading '" + document + "'")
        elif step == DocSearch.INDEX_STEP_SORTING:
            self.progressBar.set_text("Sorting")
        gtk_refresh()

    def _open_search_window(self, objsrc):
        self.progressBar.set_text("Loading documents ...");
        self.progressBar.set_fraction(0.0)
        dsearch = DocSearch(self.config.workdir, self._docsearch_callback)
        SearchWindow(dsearch)
        self.progressBar.set_text("");
        self.progressBar.set_fraction(0.0)

    def _connect_signals(self):
        self.mainWindow.connect("destroy", lambda x: self.destroy())
        self.wTree.get_object("toolbuttonQuit").connect("clicked", lambda x: self._destroy())
        self.wTree.get_object("menuitemQuit").connect("activate", lambda x: self._destroy())

        self.wTree.get_object("menuitemAbout").connect("activate", lambda x: AboutDialog())

        self.wTree.get_object("menuitemSettings").connect("activate", lambda x: SettingsWindow(self.config))

        self.wTree.get_object("toolbuttonSearch").connect("clicked", self._open_search_window)
        self.wTree.get_object("menuitemSearch").connect("activate", self._open_search_window)

    def _destroy(self):
        self.wTree.get_object("mainWindow").destroy()
        gtk.main_quit()

