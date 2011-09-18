import gtk
import os

from util import gtk_refresh
from util import load_uifile

from aboutdialog import AboutDialog
from doc import ScannedDoc
from docsearch import DocSearch
from searchwindow import SearchWindow
from settingswindow import SettingsWindow

class MainWindow:
    WIN_TITLE = "Paperwork"

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
        self.pageEventBox = self.wTree.get_object("eventboxImg")
        self.pageTxt = self.wTree.get_object("textviewPageTxt")
        self.pageVpaned = self.wTree.get_object("vpanedPage")

        self.page_scaled = True
        self.new_document()

        self._connect_signals()
        self.mainWindow.set_visible(True)

    def _docsearch_callback(self, step, progression, total, document=None):
        self.progressBar.set_fraction(float(progression) / total)
        if step == DocSearch.INDEX_STEP_READING:
            self.progressBar.set_text("Reading '" + document + "' ... ") # TODO(Jflesch): i18n/l10n
        elif step == DocSearch.INDEX_STEP_SORTING:
            self.progressBar.set_text("Sorting ... ") # TODO(Jflesch): i18n/l10n
        gtk_refresh()

    def _show_busy_cursor(self):
        watch = gtk.gdk.Cursor(gtk.gdk.WATCH)
        self.mainWindow.window.set_cursor(watch)
        gtk_refresh()

    def _show_normal_cursor(self):
        self.mainWindow.window.set_cursor(None)

    def _check_workdir(self):
        try:
            os.stat(self.config.workdir)
        except OSError, e:
            print "Unable to stat dir '%s': %s --> opening dialog settings" % (self.config.workdir, e)
            SettingsWindow(self.config)
            return

    def _open_search_window(self, objsrc):
        self._check_workdir()
    
        self._show_busy_cursor()
        try:
            self.progressBar.set_text("Loading documents ...");
            self.progressBar.set_fraction(0.0)
            dsearch = DocSearch(self.config.workdir, self._docsearch_callback)
            SearchWindow(self, dsearch)
        finally:
            self.progressBar.set_text("");
            self.progressBar.set_fraction(0.0)
            self._show_normal_cursor()

    def _show_page_img(self, page):
        filepath = self.doc.get_img_path(page)

        if self.page_scaled:
            pixbuf = gtk.gdk.pixbuf_new_from_file(filepath)
            # we strip 30 pixels from the width of scrolled window, because the vertical scrollbar
            # is not included
            # TODO(Jflesch): Figure out a way to get the exact scrollbar width
            wantedWidth = self.pageScrollWin.get_allocation().width - 30;
            if pixbuf.get_width() > wantedWidth:
                ratio = float(wantedWidth) / pixbuf.get_width();
                wantedHeight = int(ratio * pixbuf.get_height())
                self.pageImg.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND1))
            else:
                wantedWidth = pixbuf.get_width()
                wantedHeight = pixbuf.get_height()
                self.pageImg.window.set_cursor(None)
            scaled_pixbuf = pixbuf.scale_simple(wantedWidth, wantedHeight, gtk.gdk.INTERP_BILINEAR)
            self.pageImg.set_from_pixbuf(scaled_pixbuf)
        else:
            self.pageImg.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND1))
            self.pageImg.set_from_file(filepath)
        self.pageImg.show()

    def _show_page_txt(self, page):
        txt = self.doc.get_text(page)
        self.pageTxt.get_buffer().set_text(txt)

    def _reset_vpaned(self):
        wantedSplitPos = (self.pageVpaned.get_allocation().height) * 3 / 4;
        self.pageVpaned.set_position(wantedSplitPos)

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

        self.page_scaled = True

        print "Showing page %d" % (page)

        self.pageListUI.get_selection().select_path((page-1))
        try:
            self._show_page_img(page)
        except Exception, e:
            self.pageImg.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_BUTTON)
        try:
            self._show_page_txt(page)
        except Exception, e:
            print "Unable to show text for doc '%s': %s" % (self.doc, e)
            self.pageTxt.get_buffer().set_text("")

    def refresh_page(self):
        print "Refreshing main window"
        self._show_page_img(self._get_current_page())
        self._reset_vpaned()

    def _change_scale(self, objsrc = None, x = None, y = None):
        print "Changing scaling: %d -> %d" % (self.page_scaled, not self.page_scaled)
        self.page_scaled = not self.page_scaled
        self._show_page_img(self._get_current_page())

    def _scan_callback(self, step, progression, total):
        self.progressBar.set_fraction(float(progression) / total)
        if step == ScannedDoc.SCAN_STEP_SCAN:
            self.progressBar.set_text("Scanning ... ") # TODO(Jflesch): i18n/l10n
        elif step == ScannedDoc.SCAN_STEP_OCR:
            self.progressBar.set_text("Reading ... ") # TODO(Jflesch): i18n/l10n
        gtk_refresh()

    def _refresh_page_list(self):
        self.pageList.clear()
        for page in range(1, self.doc.get_nb_pages()+1):
            self.pageList.append([ "Page %d" % (page) ]) # TODO: i18n/l10n

    def _scan_next_page(self, objsrc = None):
        self._check_workdir()
    
        self._show_busy_cursor()
        try:
            self.doc.scan_next_page(self.config.ocrlang, self._scan_callback)
            self._refresh_page_list()
            self._show_page(page = self.doc.get_nb_pages())
        finally:
            self.progressBar.set_text("");
            self.progressBar.set_fraction(0.0)
            self._show_normal_cursor()

    def _connect_signals(self):
        self.mainWindow.connect("destroy", lambda x: self._destroy())
        self.wTree.get_object("menuitemNew").connect("activate", self.new_document)
        self.wTree.get_object("toolbuttonNew").connect("clicked", self.new_document)
        self.wTree.get_object("toolbuttonQuit").connect("clicked", lambda x: self._destroy())
        self.wTree.get_object("menuitemScan").connect("activate", self._scan_next_page)
        self.wTree.get_object("toolbuttonScan").connect("clicked", self._scan_next_page)
        self.wTree.get_object("menuitemQuit").connect("activate", lambda x: self._destroy())

        self.wTree.get_object("menuitemAbout").connect("activate", lambda x: AboutDialog())

        self.wTree.get_object("menuitemSettings").connect("activate", lambda x: SettingsWindow(self, self.config))

        self.wTree.get_object("toolbuttonSearch").connect("clicked", self._open_search_window)
        self.wTree.get_object("menuitemSearch").connect("activate", self._open_search_window)
        self.pageListUI.connect("cursor-changed", self._show_page)
        self.pageEventBox.connect("button-press-event", self._change_scale)

    def _destroy(self):
        self.wTree.get_object("mainWindow").destroy()
        gtk.main_quit()

    def _show_doc(self, doc = None):
        """
        Arguments:
            doc --- doc.ScannedDoc (see docsearch.DocSearch.get_doc())
        """
        if doc != None:
            self.doc = doc
        else:
            assert(self.doc)
        self.page = 1

        self.mainWindow.set_title(str(self.doc) + " - " + self.WIN_TITLE)
        self._refresh_page_list()
        self._show_page(page = 1)

    def show_doc(self, doc):
        self._show_doc(doc)
        self._reset_vpaned()

    def new_document(self, objsrc = None):
        self._show_doc(ScannedDoc(self.config.workdir)) # new document

