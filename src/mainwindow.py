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
        assert(self.mainWindow)
        self.progressBar = self.wTree.get_object("progressbarMainWin")
        self.pageList = self.wTree.get_object("liststorePage")
        self.pageListUI = self.wTree.get_object("treeviewPage")
        self.pageScrollWin = self.wTree.get_object("scrolledwindowPageImg")
        self.pageImg = self.wTree.get_object("imagePageImg")
        self.pageTxt = self.wTree.get_object("textviewPageTxt")

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
        SearchWindow(self, dsearch)
        self.progressBar.set_text("");
        self.progressBar.set_fraction(0.0)

    def _show_page_img(self, page):
        filepath = self.doc.get_img_path(page)
        pixbuf = gtk.gdk.pixbuf_new_from_file(filepath)

        # we strip 30 pixels from the width of scrolled window, because the vertical scrollbar
        # is not included
        # TODO(Jflesch): Figure out a way to get the exact scrollbar width
        wantedWidth = self.pageScrollWin.get_allocation().width - 30;
        if pixbuf.get_width() > wantedWidth:
            ratio = float(wantedWidth) / pixbuf.get_width();
            wantedHeight = int(ratio * pixbuf.get_height())
        else:
            wantedWidth = pixbuf.get_width()
            wantedHeight = pixbuf.get_height()
        scaled_pixbuf = pixbuf.scale_simple(wantedWidth, wantedHeight, gtk.gdk.INTERP_BILINEAR)
        self.pageImg.set_from_pixbuf(scaled_pixbuf)
        self.pageImg.show()

    def _show_page_txt(self, page):
        txt = self.doc.get_text(page)
        self.pageTxt.get_buffer().set_text(txt)

    def _get_current_page(self):
        selectionPath = self.pageListUI.get_selection().get_selected()
        if selectionPath[1] == None:
            raise Exception("No page selected yet")
        selection = selectionPath[0].get_value(selectionPath[1], 0)
        page = int(selection[5:]) # TODO(Jflesch): i18n/l10n
        return page

    def _show_page(self, objsrc = None, page = 0):
        if page == 0:
            page = self._get_current_page()

        print "Showing page %d" % (page)

        self.pageListUI.get_selection().select_path((page-1))
        self._show_page_img(page)
        try:
            self._show_page_txt(page)
        except Exception, e:
            print "Unable to show text for doc '%s': %s" % (self.doc, e)

    def refresh_page(self):
        print "Refreshing page"
        self._show_page_img(self._get_current_page())

    def _connect_signals(self):
        self.mainWindow.connect("destroy", lambda x: self._destroy())
        self.wTree.get_object("toolbuttonQuit").connect("clicked", lambda x: self._destroy())
        self.wTree.get_object("menuitemQuit").connect("activate", lambda x: self._destroy())

        self.wTree.get_object("menuitemAbout").connect("activate", lambda x: AboutDialog())

        self.wTree.get_object("menuitemSettings").connect("activate", lambda x: SettingsWindow(self.config))

        self.wTree.get_object("toolbuttonSearch").connect("clicked", self._open_search_window)
        self.wTree.get_object("menuitemSearch").connect("activate", self._open_search_window)
        self.pageListUI.connect("cursor-changed", self._show_page)

    def _destroy(self):
        self.wTree.get_object("mainWindow").destroy()
        gtk.main_quit()

    def show_doc(self, doc):
        """
        Arguments:
            doc --- doc.DtGrepDoc (see docsearch.DocSearch.get_doc())
        """
        self.doc = doc
        self.page = 1

        self.pageList.clear()
        for page in range(1, doc.get_nb_pages()+1):
            self.pageList.append([ "Page %d" % (page) ]) # TODO: i18n/l10n

        self._show_page(page = 1)



