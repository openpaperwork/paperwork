"""
Code relative to the main window management.
"""

import os

import gtk

from aboutdialog import AboutDialog
from doc import ScannedDoc
from page import ScannedPage
from docsearch import DocSearch
from scanner import PaperworkScanner
from settingswindow import SettingsWindow
from labels import LabelEditor
from util import gtk_refresh
from util import image2pixbuf
from util import load_uifile
from util import SPLIT_KEYWORDS_REGEX
from util import strip_accents


class MainWindow:
    """
    Paperwork main window
    """

    WIN_TITLE = "Paperwork"

    def __init__(self, config):
        self.__config = config

        self.__device = PaperworkScanner()
        self.__doc = None
        self.__page = None
        self.__docsearch = None
        self.__page_cache = None
        self.__win_size = None  # main window size (None = unknown yet)
        self.__label_name_to_obj = {}

        self.__widget_tree = load_uifile("mainwindow.glade")

        # the gtk window is a public attribute: dialogs need it
        self.main_window = self.__widget_tree.get_object("mainWindow")
        assert(self.main_window)
        self.__progress_bar = \
                self.__widget_tree.get_object("progressbarMainWin")
        self.__page_scroll_win = \
                self.__widget_tree.get_object("scrolledwindowPageImg")
        self.__page_img = self.__widget_tree.get_object("imagePageImg")
        self.__page_event_box = self.__widget_tree.get_object("eventboxImg")
        self.__page_txt = self.__widget_tree.get_object("textviewPageTxt")
        self.__page_vpaned = self.__widget_tree.get_object("vpanedPage")
        self.__show_all_boxes = \
                self.__widget_tree.get_object("checkmenuitemShowAllBoxes")

        # search
        self.__liststore_suggestion = \
                self.__widget_tree.get_object("liststoreSuggestion")
        self.__search_field = self.__widget_tree.get_object("entrySearch")
        self.__search_completion = gtk.EntryCompletion()
        self.__search_completion.set_model(self.__liststore_suggestion)
        self.__search_completion.set_text_column(0)
        self.__search_completion.set_match_func(lambda x, y, z: True)
        self.__search_field.set_completion(self.__search_completion)
        self.__match_list_ui = self.__widget_tree.get_object("treeviewMatch")
        self.__match_list = self.__widget_tree.get_object("liststoreMatch")
        self.__selectors = self.__widget_tree.get_object("notebookSelectors")
        self.__selectors.set_current_page(1)    # Page tab

        # page selector
        self.__page_list = self.__widget_tree.get_object("liststorePage")
        self.__page_list_ui = self.__widget_tree.get_object("treeviewPage")

        # label selector
        self.__label_list = self.__widget_tree.get_object("liststoreLabel")

        self.__widget_tree.get_object("menuitemScan") \
                .set_sensitive(self.__device.state[0])
        self.__widget_tree.get_object("toolbuttonScan") \
                .set_sensitive(self.__device.state[0])
        tooltip = gtk.Tooltips()
        tooltip.set_tip(self.__widget_tree.get_object("toolbuttonScan"),
                        self.__device.state[1])

        self.__page_scaled = True
        self.new_document()

        self.__connect_signals()
        self.main_window.set_visible(True)
        gtk_refresh()

        self.__check_workdir()

        self.__show_busy_cursor()
        self.reindex()

    def reindex(self):
        """
        Reload and reindex all the documents
        """
        try:
            self.__show_busy_cursor()
            self.__progress_bar.set_text("Loading documents ...")
            self.__progress_bar.set_fraction(0.0)
            self.__docsearch = DocSearch(self.__config.workdir,
                                       self.__cb_progress)
        finally:
            self.__progress_bar.set_text("")
            self.__progress_bar.set_fraction(0.0)
            self.__show_normal_cursor()
        self.__refresh_label_list()

    def __update_results_cb(self, objsrc=None):
        """
        Update the suggestions list and the matching documents list based on
        the keywords typed by the user in the search field.
        """
        txt = unicode(self.__search_field.get_text())
        keywords = SPLIT_KEYWORDS_REGEX.split(txt)
        print "Search: %s" % (str(keywords))

        suggestions = self.__docsearch.find_suggestions(keywords)
        print "Got %d suggestions" % len(suggestions)
        self.__liststore_suggestion.clear()
        for suggestion in suggestions:
            txt = ""
            for word in suggestion:
                if txt != "":
                    txt += " "
                txt += word
            self.__liststore_suggestion.append([txt])

        documents = self.__docsearch.find_documents(keywords)
        print "Got %d documents" % len(documents)
        self.__match_list.clear()
        for document in reversed(documents):
            doc = self.__docsearch.docs[document]
            label_str = ""
            for label in doc.labels:
                label_str += "\n  "
                label_str += str(label)
            self.__match_list.append([(document + label_str)])

    def __show_selected_doc_cb(self, objsrc=None):
        """
        Show the currently selected document
        """
        selection_path = self.__match_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No document selected. Can't open"
            return False
        selection = selection_path[0].get_value(selection_path[1], 0)
        selection = selection.split("\n")[0]
        doc = self.__docsearch.docs[selection]

        print "Showing doc %s" % selection
        self.show_doc(doc)
        return True

    def __show_busy_cursor(self):
        """
        Turn the mouse cursor into one indicating that the program is currently
        busy.
        """
        watch = gtk.gdk.Cursor(gtk.gdk.WATCH)
        self.main_window.window.set_cursor(watch)
        gtk_refresh()

    def __show_normal_cursor(self):
        """
        Make sure the mouse cursor if the default one.
        """
        self.main_window.window.set_cursor(None)

    def __check_workdir(self):
        """
        Check that the current work dir (see config.PaperworkConfig) exists. If
        not, open the settings dialog.
        """
        try:
            os.stat(self.__config.workdir)
        except OSError, exc:
            print ("Unable to stat dir '%s': %s --> opening dialog settings"
                   % (self.__config.workdir, exc))
            SettingsWindow(self, self.__config)
            return

    def __get_keywords(self):
        """
        Get the keywords currently typed in the search field by the user
        """
        txt = unicode(self.__search_field.get_text())
        txt = txt.lower()
        words = txt.split(" ")
        for i in range(0, len(words)):
            words[i] = words[i].strip()
            words[i] = strip_accents(words[i])
        return words

    def __show_page_img(self, page):
        """
        Show the page image
        """
        self.__progress_bar.set_fraction(0.0)
        # TODO(Jflesch): i18n/l10n
        self.__progress_bar.set_text("Loading image and text ...")
        try:
            if self.__page_scaled:
                progress_callback = lambda \
                        progression, total, step = None, doc = None: \
                        self.__cb_progress(progression, total + (total / 3),
                                           step, doc)
            else:
                progress_callback = self.__cb_progress

            # Finding word boxes can be pretty slow, so we keep in memory the
            # last image and try to reuse it:
            if self.__page_cache == None or self.__page_cache[0] != page:
                self.__page_cache = (page, page.img,
                                   page.get_boxes(progress_callback))
            img = self.__page_cache[1].copy()
            boxes = self.__page_cache[2]

            if self.__show_all_boxes.get_active():
                page.draw_boxes(img, boxes, color=(0x6c, 0x5d, 0xd1), width=1)
            page.draw_boxes(img, boxes, color=(0x00, 0x9f, 0x00), width=5,
                            keywords=self.__get_keywords())

            pixbuf = image2pixbuf(img)

            if self.__page_scaled:
                # TODO(Jflesch): i18n/l10n
                self.__progress_bar.set_text("Resizing the image ...")
                gtk_refresh()

                # we strip 30 pixels from the width of scrolled window, because
                # the vertical scrollbar is not included
                # TODO(Jflesch): Figure out a way to get the exact scrollbar
                # width
                wanted_width = (self.__page_scroll_win.get_allocation().width
                                - 30)
                if pixbuf.get_width() > wanted_width:
                    ratio = float(wanted_width) / pixbuf.get_width()
                    wanted_height = int(ratio * pixbuf.get_height())
                    self.__page_img.window.set_cursor(
                            gtk.gdk.Cursor(gtk.gdk.HAND1))
                else:
                    wanted_width = pixbuf.get_width()
                    wanted_height = pixbuf.get_height()
                    self.__page_img.window.set_cursor(None)
                pixbuf = pixbuf.scale_simple(wanted_width, wanted_height,
                                             gtk.gdk.INTERP_BILINEAR)
            else:
                self.__page_img.window \
                        .set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND1))

            self.__page_img.set_from_pixbuf(pixbuf)
            self.__page_img.show()
        finally:
            self.__progress_bar.set_fraction(0.0)
            self.__progress_bar.set_text("")

    def __show_page_txt(self, page):
        """
        Update the page text
        """
        txt = "\n".join(page.text)
        self.__page_txt.get_buffer().set_text(txt)

    def __reset_page_vpaned(self):
        """
        Reset the position of the vpaned between the page image and the page
        text (which is hidden by default)
        """
        # keep the vpane as hidden as possible
        self.__page_vpaned.set_position(0)

    def __get_selected_page(self):
        """
        Return and instance of page.ScannedPage representing the currently
        selected page.
        """
        selection_path = self.__page_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            raise Exception("No page selected yet")
        selection = selection_path[0].get_value(selection_path[1], 0)
        # TODO(Jflesch): i18n/l10n
        page = self.__doc.pages[(int(selection[5:]) - 1)]
        return page

    def __get_current_page(self):
        """
        Returns the page being currently displayed
        """
        return self.__page

    def __show_page(self, page=None):
        """
        Display the specified page
        """
        if page == None:
            page = self.__get_current_page()

        self.__page = page
        self.__page_scaled = True

        print "Showing page '%s'" % (page)

        self.__page_list_ui.get_selection().select_path(page.page_nb)
        try:
            self.__show_page_img(page)
        except IOError, exc:
            print "Unable to show image for '%s': %s" % (page, exc)
            self.__page_img.set_from_stock(gtk.STOCK_MISSING_IMAGE,
                                        gtk.ICON_SIZE_BUTTON)
        try:
            self.__show_page_txt(page)
        except IOError, exc:
            print "Unable to show text for doc '%s': %s" % (page, exc)
            self.__page_txt.get_buffer().set_text("")

    def __show_selected_page_cb(self, objsrc=None):
        """
        Find the currently selected page, and display it accordingly
        """
        page = self.__get_selected_page()
        print "Showing selected page: %s" % (page)
        self.__show_page(page)

    def __refresh_page(self):
        """
        Refresh the display of the current page.
        """
        print "Refreshing main window"
        self.__show_page_img(self.__get_current_page())
        self.__reset_page_vpaned()

    def __change_scale_cb(self, objsrc=None, mouse_x=None, mouse_y=None):
        """
        Switch the scale mode of the page display. Will switch between 1:1
        display and adapted-to-the-window-size display.
        """
        print "Changing scaling: %d -> %d" % (self.__page_scaled,
                                              not self.__page_scaled)
        self.__page_scaled = not self.__page_scaled
        self.__refresh_page()

    def __cb_progress(self, progression, total, step=None, doc=None):
        """
        Update the main progress bar
        """
        self.__progress_bar.set_fraction(float(progression) / total)
        if step == ScannedPage.SCAN_STEP_SCAN:
            # TODO(Jflesch): i18n/l10n
            self.__progress_bar.set_text("Scanning ... ")
        elif step == ScannedPage.SCAN_STEP_OCR:
            # TODO(Jflesch): i18n/l10n
            self.__progress_bar.set_text("Reading ... ")
        elif step == DocSearch.INDEX_STEP_READING:
            # TODO(Jflesch): i18n/l10n
            self.__progress_bar.set_text("Reading '%s' ... " % (doc))
        elif step == DocSearch.INDEX_STEP_SORTING:
            # TODO(Jflesch): i18n/l10n
            self.__progress_bar.set_text("Sorting ... ")
        gtk_refresh()

    def __refresh_page_list(self):
        """
        Reload and refresh the page list
        """
        self.__page_list.clear()
        for page in range(1, self.__doc.nb_pages + 1):
            self.__page_list.append(["Page %d" % (page)])   # TODO: i18n/l10n

    def __refresh_label_list(self):
        """
        Reload and refresh the label list
        """
        self.__label_name_to_obj = {}
        self.__label_list.clear()
        if self.__docsearch != None and self.__doc != None:
            labels = self.__doc.labels
            for label in self.__docsearch.label_list:
                self.__label_name_to_obj[str(label)] = label
                self.__label_list.append([str(label), (label in labels)])

    def __scan_next_page_cb(self, objsrc=None):
        """
        Scan a new page and append it to the current document
        """
        self.__check_workdir()

        self.__selectors.set_current_page(1)    # Page tab

        self.__show_busy_cursor()
        try:
            self.__doc.scan_next_page(self.__device, self.__config.ocrlang,
                                    self.__cb_progress)
            page = self.__doc.pages[self.__doc.nb_pages - 1]
            self.__docsearch.index_page(page)
            self.__refresh_page_list()
            self.__show_page(page)
            self.__reset_page_vpaned()
        finally:
            self.__progress_bar.set_text("")
            self.__progress_bar.set_fraction(0.0)
            self.__show_normal_cursor()

    def __destroy_doc_cb(self, objsrc=None):
        """
        Ask for confirmation and then delete the document being viewed.
        """
        confirm = gtk.MessageDialog(parent=self.main_window,
                flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                type=gtk.MESSAGE_WARNING,
                buttons=gtk.BUTTONS_YES_NO,
                message_format="Are you sure ?")  # TODO(Jflesch): i18n/l10n
        response = confirm.run()
        confirm.destroy()
        if response != gtk.RESPONSE_YES:
            print "Deletion aborted"
            return
        print "Deleting ..."
        self.__doc.destroy()
        self.new_document()
        print "Deleted"
        self.reindex()

    def __print_doc_cb(self, objsrc=None):
        """
        Print the document being viewed. Will display first a printing dialog.
        """
        print_op = gtk.PrintOperation()

        print_settings = gtk.PrintSettings()
        # By default, print context are using 72 dpi, but print_draw_page
        # will change it to 300 dpi --> we have to tell PrintOperation to scale
        print_settings.set_scale(100.0 * (72.0 / ScannedPage.PRINT_RESOLUTION))
        print_op.set_print_settings(print_settings)

        print_op.set_n_pages(self.__doc.nb_pages)
        print_op.set_current_page(self.__get_current_page().page_nb)
        print_op.set_use_full_page(True)
        print_op.set_job_name(str(self.__doc))
        print_op.set_export_filename(str(self.__doc) + ".pdf")
        print_op.set_allow_async(True)
        print_op.connect("draw-page", self.__doc.print_page_cb)
        print_op.run(gtk.PRINT_OPERATION_ACTION_PRINT_DIALOG,
                     self.main_window)

    def __clear_search_cb(self, objsrc=None):
        """
        Clear the search field.
        """
        self.__search_field.set_text("")
        self.__selectors.set_current_page(0)    # Documents tab

    def __redo_ocr_on_all_cb(self, src=None):
        """
        Redo the OCR all *all* the documents
        """
        # TODO(Jflesch): i18n/l10n
        msg = "This may take a very long time\nAre you sure ?"
        confirm = gtk.MessageDialog(parent=self.main_window,
                flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                type=gtk.MESSAGE_WARNING,
                buttons=gtk.BUTTONS_YES_NO,
                message_format=msg)
        response = confirm.run()
        confirm.destroy()
        if response != gtk.RESPONSE_YES:
            print "Massive OCR canceled"
            return
        try:
            self.__show_busy_cursor()
            self.__progress_bar.set_text("Rereading all documents ...")
            self.__progress_bar.set_fraction(0.0)
            self.__docsearch.redo_ocr(self.__cb_progress,
                                    self.__config.ocrlang)
        finally:
            self.__progress_bar.set_text("")
            self.__progress_bar.set_fraction(0.0)
            self.__show_normal_cursor()
        self.reindex()

    def __on_resize_cb(self, window=None, allocation=None):
        """
        Called each time the main window is resized
        """
        if self.__win_size != allocation:
            print "Main window resized"
            self.__win_size = allocation
            self.__reset_page_vpaned()

    def __add_label_cb(self, objsrc=None):
        """
        Open the dialog to add a new label, and use it to create the label
        """
        labeleditor = LabelEditor()
        if labeleditor.edit(self.main_window):
            print "Adding label %s to doc %s" % (str(labeleditor.label),
                                                 str(self.__doc))
            self.__doc.add_label(labeleditor.label)
            self.__docsearch.add_label(labeleditor.label, self.__doc)
        self.__refresh_label_list()

    def __label_toggled_cb(self, renderer, objpath):
        """
        Take into account changes made on the checkboxes of labels
        """
        label = self.__label_name_to_obj[self.__label_list[objpath][0]]
        if label in self.__doc.labels:
            self.__doc.remove_label(label)
        else:
            self.__doc.add_label(label)
        self.__refresh_label_list()

    def __show_about_dialog_cb(self, objsrc=None):
        """
        Create and show the about dialog.
        """
        about = AboutDialog(self.main_window)
        about.show()

    def __connect_signals(self):
        """
        Connect all the main window signals to their callbacks
        """
        self.main_window.connect("destroy", lambda x: self.__destroy())
        self.main_window.connect("size-allocate", self.__on_resize_cb)
        self.__widget_tree.get_object("menuitemNew").connect("activate",
                self.new_document)
        self.__widget_tree.get_object("toolbuttonNew").connect("clicked",
                self.new_document)
        self.__widget_tree.get_object("toolbuttonQuit").connect("clicked",
                lambda x: self.__destroy())
        self.__widget_tree.get_object("menuitemScan").connect("activate",
                self.__scan_next_page_cb)
        self.__widget_tree.get_object("toolbuttonScan").connect("clicked",
                self.__scan_next_page_cb)
        self.__widget_tree.get_object("menuitemDestroy").connect("activate",
                self.__destroy_doc_cb)
        self.__widget_tree.get_object("toolbuttonPrint").connect("clicked",
                self.__print_doc_cb)
        self.__widget_tree.get_object("menuitemPrint").connect("activate",
                self.__print_doc_cb)
        self.__widget_tree.get_object("menuitemQuit").connect("activate",
                lambda x: self.__destroy())
        self.__widget_tree.get_object("menuitemAbout").connect("activate",
                self.__show_about_dialog_cb)
        self.__widget_tree.get_object("menuitemSettings").connect("activate",
                lambda x: SettingsWindow(self, self.__config))
        self.__widget_tree.get_object("buttonSearchClear").connect("clicked",
                self.__clear_search_cb)
        self.__widget_tree.get_object("menuitemReOcrAll").connect("activate",
                self.__redo_ocr_on_all_cb)
        self.__widget_tree.get_object("buttonAddLabel").connect("clicked",
                self.__add_label_cb)
        self.__widget_tree.get_object("cellrenderertoggle1").connect("toggled",
                self.__label_toggled_cb)
        self.__search_field.connect("focus-in-event",
                lambda x, y: self.__selectors.set_current_page(0))  # Doc tab
        self.__page_list_ui.connect("cursor-changed",
                self.__show_selected_page_cb)
        self.__page_event_box.connect("button-press-event",
                                      self.__change_scale_cb)
        self.__search_field.connect("changed", self.__update_results_cb)
        self.__match_list_ui.connect("cursor-changed",
                self.__show_selected_doc_cb)
        self.__show_all_boxes.connect("activate",
                lambda x: self.__refresh_page())

    def __destroy(self):
        """
        Destroy the main window and all its associated widgets
        """
        self.main_window.destroy()
        gtk.main_quit()

    def cleanup(self):
        """
        Uninit what has been init by the __init__() function
        """
        if self.__device != None:
            self.__device.close()

    def __show_doc(self, doc=None):
        """
        Arguments:
            doc --- doc.ScannedDoc (see docsearch.DocSearch.docs[])
        """
        if doc != None:
            self.__doc = doc
        else:
            assert(self.__doc)

        self.main_window.set_title(str(self.__doc) + " - " + self.WIN_TITLE)
        self.__refresh_page_list()
        self.__page = self.__doc.pages[0]
        print "Showing first page of the doc"
        self.__show_page(self.__page)
        self.__refresh_label_list()

    def show_doc(self, doc):
        """
        Display the specified document
        """
        self.__show_doc(doc)
        self.__reset_page_vpaned()

    def new_document(self, objsrc=None):
        """
        Start the edition of the new document.
        """
        self.__selectors.set_current_page(1)    # Page tab
        self.__show_doc(ScannedDoc(self.__config.workdir))  # new document
