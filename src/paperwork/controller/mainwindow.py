"""
Code relative to the main window management.
"""

from copy import copy
import ImageDraw
import os
import time

import gettext
import gtk

from paperwork.controller.aboutdialog import AboutDialog
from paperwork.controller.settingswindow import SettingsWindow
from paperwork.model.doc import ScannedDoc
from paperwork.model.docsearch import DocSearch
from paperwork.model.labels import LabelEditor
from paperwork.model.page import ScannedPage
from paperwork.model.scanner import PaperworkScanner
from paperwork.util import gtk_refresh
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile
from paperwork.util import MIN_KEYWORD_LEN
from paperwork.util import split_words

_ = gettext.gettext


class Tabs(object):
    """
    The 3 tabs on the left of the main window. Include the search field and its
    buttons.
    """

    TAB_DOCUMENTS = 0
    TAB_PAGES = 1
    TAB_LABELS = 2

    def __init__(self, main_win, widget_tree):
        tooltips = gtk.Tooltips()

        self.__main_win = main_win
        self.__widget_tree = widget_tree

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
        self.show_tab(self.TAB_PAGES)
        self.__match_list_menu = \
                self.__widget_tree.get_object("popupmenuMatchs")

        tooltips.set_tip(self.__search_field,
                        (_('Search documents\n')
                         + _('\'!\' can be used as a prefix to')
                         + _(' negate a keyword')))

        # page selector
        self.__page_list = self.__widget_tree.get_object("liststorePage")
        self.__page_list_ui = self.__widget_tree.get_object("treeviewPage")
        self.__page_list_menu = self.__widget_tree.get_object("popupmenuPages")

        # label selector
        self.__label_list = self.__widget_tree.get_object("liststoreLabel")
        self.__label_list_ui = self.__widget_tree.get_object("treeviewLabel")
        self.__label_list_menu = \
                self.__widget_tree.get_object("popupmenuLabels")
        self.__connect_signals()

    def set_result_lists_sensitive(self, state):
        """
        Used to indicates if document and label list must accept user input.
        They usually don't when we reloading all the documents.

        Arguments:
            state --- True if they should, False if they shouldn't
        """
        if state == False:
            self.__match_list.clear()
            self.__label_list.clear()
        else:
            self.refresh_label_list()
            self.__update_results_cb()
        self.__match_list_ui.set_sensitive(state)
        self.__label_list_ui.set_sensitive(state)

    def set_page_changers_sensitive(self, state):
        """
        Used to indicate if the user input must be blocked from any
        element that would change the page being displayed.
        Usually used when a page is being loaded.

        Arguments:
            state --- True if they should, False if they shouldn't
        """
        self.__match_list_ui.set_sensitive(state)
        self.__page_list_ui.set_sensitive(state)

    def __show_selected_doc_cb(self, objsrc=None):
        """
        Show the currently selected document
        """
        selection_path = self.__match_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No document selected. Can't open"
            return False
        doc = selection_path[0].get_value(selection_path[1], 1)

        print "Showing doc %s" % doc
        self.__main_win.doc = doc
        return True

    def __get_selected_page(self):
        """
        Return and instance of page.ScannedPage representing the currently
        selected page.
        """
        selection_path = self.__page_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            raise Exception("No page selected yet")
        selection = selection_path[0].get_value(selection_path[1], 0)
        page = self.__main_win.doc.pages[(int(selection[5:]) - 1)]
        return page

    def __show_selected_page_cb(self, objsrc=None):
        """
        Find the currently selected page, and display it accordingly
        """
        page = self.__get_selected_page()
        print "Showing selected page: %s" % (page)
        self.__main_win.page = page
        return True

    def get_search_sentence(self):
        """
        Get the sentence currently typed in the search field by the user
        """
        return unicode(self.__search_field.get_text())

    def show_doc_list(self, docs):
        self.__match_list.clear()
        for doc in docs:
            labels = doc.labels
            final_str = doc.name
            if len(labels) > 0:
                final_str += ("\n  "
                        + "\n  ".join([x.get_html() for x in labels]))
            self.__match_list.append([final_str, doc])

    def __update_results_cb(self, objsrc=None):
        """
        Called when the user change the content of the search field
        """
        self.refresh_doc_list()

    def __destroy_current_doc_cb(self, objsrc=None):
        """
        Destroy/delete the currently active document
        """
        self.__main_win.destroy_doc(self.__main_win.doc)

    def __destroy_current_page_cb(self, widget=None):
        """
        Destroy/delete the currently active page
        """
        self.__main_win.destroy_page(self.__main_win.page)

    def __clear_search_cb(self, entry=None, iconpos=None, event=None):
        """
        Clear the search field.
        """
        self.__search_field.set_text("")
        self.show_tab(self.TAB_DOCUMENTS)

    def refresh_label_list(self):
        """
        Reload and refresh the label list
        """
        self.__label_list.clear()
        if self.__main_win.docsearch != None and self.__main_win.doc != None:
            labels = self.__main_win.doc.labels
            for label in self.__main_win.docsearch.label_list:
                self.__label_list.append([label.get_html(), (label in labels),
                                          label])

    def refresh_page_list(self):
        """
        Reload and refresh the page list
        """
        self.__page_list.clear()
        for page in range(1, self.__main_win.doc.nb_pages + 1):
            self.__page_list.append([_('Page %d') % (page)])

    def refresh_doc_list(self):
        """
        Update the suggestions list and the matching documents list based on
        the keywords typed by the user in the search field.
        """
        if self.__main_win.docsearch == None:
            return
        sentence = self.get_search_sentence()
        print "Search: %s" % (sentence.encode('ascii', 'replace'))

        suggestions = self.__main_win.docsearch.find_suggestions(sentence)
        print "Got %d suggestions" % len(suggestions)
        self.__liststore_suggestion.clear()
        for suggestion in suggestions:
            self.__liststore_suggestion.append([suggestion])

        documents = self.__main_win.docsearch.find_documents(sentence)
        print "Got %d documents" % len(documents)
        self.show_doc_list(reversed(documents))

    def __add_label_cb(self, objsrc=None):
        """
        Open the dialog to add a new label, and use it to create the label
        """
        labeleditor = LabelEditor()
        if labeleditor.edit(self.__main_win.main_window):
            print "Adding label %s to doc %s" % (str(labeleditor.label),
                                                 str(self.__main_win.doc))
            self.doc.add_label(labeleditor.label)
            self.docsearch.add_label(labeleditor.label, self.__main_win.doc)
        self.refresh_label_list()

    def __label_toggled_cb(self, renderer, objpath):
        """
        Take into account changes made on the checkboxes of labels
        """
        label = self.__label_list[objpath][2]
        if label in self.__main_win.doc.labels:
            self.__main_win.doc.remove_label(label)
        else:
            self.__main_win.doc.add_label(label)
        self.refresh_label_list()
        self.__update_results_cb()

    def __edit_clicked_label_cb(self, treeview=None, objpath=None,
                                view_column=None):
        """
        Called when the user click on 'edit label'
        """
        label = self.__label_list[objpath][2]
        self.__edit_label(label)

    def __apply_to_current_label_cb(self, widget, action):
        """
        Apply a given action to the currently selected label.

        Arguments:
            widget --- ignored (here so it can be used as a GTK callback)
            action --- function accepting a label as argument
        """
        selection_path = self.__label_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No label selected"
            return False

        label = selection_path[0].get_value(selection_path[1], 2)
        action(label)
        self.refresh_label_list()
        return True

    def __open_doc_cb(self, objsrc=None):
        """
        Open the currently selected document in a file manager
        """
        if self.__main_win.doc == None:
            return False
        # TODO(Jflesch): The following is absolutely not crossplatform
        os.system('xdg-open "%s"' % (self.__main_win.doc.path))

    def __pop_menu_up_cb(self, treeview, event, ui_component, popup_menu):
        """
        Callback used when the user right click on a tree view. Display
        the given popup_menu.
        """
        # we are only interested in right clicks
        if event.button != 3 or event.type != gtk.gdk.BUTTON_PRESS:
            return False
        selection_path = self.__match_list_ui.get_selection().get_selected()
        if selection_path == None:
            return False
        ev_x = int(event.x)
        ev_y = int(event.y)
        ev_time = event.time
        pathinfo = treeview.get_path_at_pos(ev_x, ev_y)
        if pathinfo is None:
            return False
        path, col, cellx, celly = pathinfo
        treeview.grab_focus()
        treeview.set_cursor(path, col, 0)
        popup_menu.popup(None, None, None, event.button, ev_time)
        return True

    def select_page(self, page):
        self.__page_list_ui.get_selection().select_path(page.page_nb)

    def show_tab(self, tab):
        self.__selectors.set_current_page(tab)

    def __new_document_cb(self, widget=None):
        self.__main_win.new_document()

    def __scan_page_cb(self, widget=None):
        self.__main_win.scan_next_page()

    def __connect_signals(self):
        """
        Connect all the signals in the tabs area
        """
        self.__widget_tree.get_object("buttonNewDoc").connect("clicked",
                self.__new_document_cb)
        self.__widget_tree.get_object("buttonDestroyDoc").connect("clicked",
                self.__destroy_current_doc_cb)
        self.__widget_tree.get_object("buttonScanPage").connect("clicked",
                self.__scan_page_cb)
        self.__widget_tree.get_object("buttonDestroyPage").connect("clicked",
                self.__destroy_current_page_cb)
        self.__widget_tree.get_object("entrySearch").connect("icon-press",
                self.__clear_search_cb)
        self.__widget_tree.get_object("buttonAddLabel").connect("clicked",
                self.__add_label_cb)
        self.__widget_tree.get_object("cellrenderertoggleLabel").connect(
                "toggled", self.__label_toggled_cb)
        self.__widget_tree.get_object("menuitemDestroyPage2").connect(
                "activate", self.__destroy_current_page_cb)
        self.__widget_tree.get_object("menuitemDestroyDoc2").connect(
                "activate", self.__destroy_current_doc_cb)
        self.__widget_tree.get_object("menuitemEditLabel").connect("activate",
                self.__apply_to_current_label_cb, self.__main_win.edit_label)
        self.__widget_tree.get_object("menuitemDestroyLabel").connect(
                "activate", self.__apply_to_current_label_cb,
                self.__main_win.destroy_label)
        self.__widget_tree.get_object("menuitemOpenDoc").connect(
                "activate", self.__open_doc_cb)
        self.__widget_tree.get_object("buttonEditLabel").connect("clicked",
                self.__apply_to_current_label_cb, self.__main_win.edit_label)
        self.__widget_tree.get_object("buttonDestroyLabel").connect("clicked",
                self.__apply_to_current_label_cb, self.__main_win.destroy_label)
        self.__search_field.connect("focus-in-event",
                lambda x, y: self.__selectors.set_current_page(0))  # Doc tab
        self.__page_list_ui.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.__page_list_ui.connect("button_press_event",
                                    self.__pop_menu_up_cb,
                                    self.__page_list_ui,
                                    self.__page_list_menu)
        self.__page_list_ui.connect("cursor-changed",
                self.__show_selected_page_cb)
        self.__search_field.connect("changed", self.__update_results_cb)
        self.__match_list_ui.connect("cursor-changed",
                self.__show_selected_doc_cb)
        self.__match_list_ui.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.__match_list_ui.connect("button_press_event",
                                    self.__pop_menu_up_cb,
                                    self.__match_list_ui,
                                    self.__match_list_menu)
        self.__label_list_ui.connect("row-activated",
                                     self.__edit_clicked_label_cb)
        self.__label_list_ui.connect("button_press_event",
                                    self.__pop_menu_up_cb,
                                    self.__label_list_ui,
                                    self.__label_list_menu)

class ImageArea(object):
    """
    Where the page image is displayed (does not include the text area)
    """

    def __init__(self, main_win, widget_tree):
        self.__main_win = main_win
        self.__widget_tree = widget_tree

        self.__page_scroll_win = \
                self.__widget_tree.get_object("scrolledwindowPageImg")
        self.__page_img = self.__widget_tree.get_object("imagePageImg")
        self.__page_event_box = self.__widget_tree.get_object("eventboxImg")
        self.__page_scaled = True

        self.__connect_signals()

    @staticmethod
    def __draw_box(draw, img_size, box, width, color):
        """
        Draw a single box. See draw_boxes()
        """
        for i in range(2, width + 2):
            ((pt_a_x, pt_a_y), (pt_b_x, pt_b_y)) = box.position
            draw.rectangle(((pt_a_x - i, pt_a_y - i),
                            (pt_b_x + i, pt_b_y + i)),
                           outline=color)

    @staticmethod
    def draw_boxes(img, boxes, color, width, sentence=None):
        """
        Draw the boxes on the image

        Arguments:
            img --- the image
            boxes --- see ScannedPage.boxes
            color --- a tuple of 3 integers (each of them being 0 < X < 256)
             indicating the color to use to draw the boxes
            width --- Width of the line of the boxes
            keywords --- only draw the boxes for these keywords (None == all
                the boxes)
        """
        if sentence != None:
            if len(sentence) < MIN_KEYWORD_LEN:
                return
            words = split_words(sentence)
            # unfold the generator
            keywords = []
            for word in words:
                keywords.append(word)
        else:
            keywords = None

        for box in boxes:
            words = split_words(box.content)
            box.content = u" ".join(words)

        draw = ImageDraw.Draw(img)
        for box in boxes:
            draw_box = (keywords == None)
            if not draw_box and keywords != None:
                for keyword in keywords:
                    if keyword in box.content:
                        draw_box = True
                        break
            if draw_box:
                ImageArea.__draw_box(draw, img.size, box, width, color)
        return img

    def show_page(self, page):
        """
        Show the page image
        """
        if page == None:
            self.__page_img.set_from_stock(gtk.STOCK_MISSING_IMAGE,
                                           gtk.ICON_SIZE_BUTTON)
            return

        self.__main_win.show_busy_cursor()
        self.__main_win.set_progress(0.0, _('Loading image and text ...'))
        try:
            if self.__page_scaled:
                progress_callback = lambda \
                        progression, total, step = None, doc = None: \
                        self.__main_win.cb_progress(progression,
                                                    total + (total / 3),
                                                    step, doc)
            else:
                progress_callback = self.__main_win.cb_progress

            img = page.img
            boxes = page.boxes

            if self.__main_win.must_show_all_boxes():
                self.draw_boxes(img, boxes, color=(0x6c, 0x5d, 0xd1), width=1)
            self.draw_boxes(img, boxes, color=(0x00, 0x9f, 0x00), width=5,
                            sentence=self.__main_win.tabs.get_search_sentence())

            pixbuf = image2pixbuf(img)

            if self.__page_scaled:
                self.__main_win.set_progress(0.5, _('Resizing the image ...'))
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
                else:
                    wanted_width = pixbuf.get_width()
                    wanted_height = pixbuf.get_height()
                pixbuf = pixbuf.scale_simple(wanted_width, wanted_height,
                                             gtk.gdk.INTERP_BILINEAR)
            self.__page_img.set_from_pixbuf(pixbuf)
            self.__page_img.show()
            self.__page_scroll_win.get_vadjustment().set_value(
                self.__page_scroll_win.get_vadjustment().get_lower())
            self.__page_scroll_win.get_hadjustment().set_value(
                self.__page_scroll_win.get_hadjustment().get_lower())
        except IOError, exc:
            print "Unable to show image for '%s': %s" % (page, exc)
            self.__page_img.set_from_stock(gtk.STOCK_MISSING_IMAGE,
                                           gtk.ICON_SIZE_BUTTON)
        finally:
            self.__main_win.set_progress(0.0, "")
            self.__main_win.show_normal_cursor()

    def show_busy_cursor(self):
        """
        Turn the mouse cursor into one indicating that the program is currently
        busy.
        """
        watch = gtk.gdk.Cursor(gtk.gdk.WATCH)
        self.__page_img.window.set_cursor(watch)

    def show_normal_cursor(self):
        """
        Make sure the mouse cursor if the default one.
        """
        self.__page_img.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND1))

    def __change_scale_cb(self, objsrc=None, mouse_x=None, mouse_y=None):
        """
        Switch the scale mode of the page display. Will switch between 1:1
        display and adapted-to-the-window-size display.
        """
        print "Changing scaling: %d -> %d" % (self.__page_scaled,
                                              not self.__page_scaled)
        self.__page_scaled = not self.__page_scaled
        self.show_page(self.__main_win.page)

    def __connect_signals(self):
        self.__page_event_box.connect("button-press-event",
                                      self.__change_scale_cb)


class MainWindow(object):
    """
    Paperwork main window
    """

    WIN_TITLE = "Paperwork"

    def __init__(self, config):
        tooltips = gtk.Tooltips()

        self.__config = config

        self.__device = PaperworkScanner()
        self.update_scanner_settings()

        self.__doc = None
        self.__page = None
        self.docsearch = None
        self.__win_size = None  # main window size (None = unknown yet)

        self.__widget_tree = load_uifile("mainwindow.glade")

        # the gtk window is a public attribute: dialogs need it
        self.main_window = self.__widget_tree.get_object("mainWindow")
        assert(self.main_window != None)

        self.__status_bar = self.__widget_tree.get_object("statusbar")
        # we use only one context for the status bar
        self.__status_context_id = \
                self.__status_bar.get_context_id("mainwindow")
        self.__progress_bar = self.__widget_tree.get_object("progressbar")

        self.__page_txt = self.__widget_tree.get_object("textviewPageTxt")
        self.__page_vpaned = self.__widget_tree.get_object("vpanedPage")
        self.__show_all_boxes = \
                self.__widget_tree.get_object("checkmenuitemShowAllBoxes")

        # various tooltips
        tooltips.set_tip(self.__widget_tree.get_object("toolbuttonNew"),
                         _("New document"))
        tooltips.set_tip(self.__widget_tree.get_object("toolbuttonQuit"),
                         _("Quit"))
        # tooltip on toolbuttonScan is set by update_scan_buttons_state()
        tooltips.set_tip(self.__widget_tree.get_object("toolbuttonPrint"),
                         _("Print"))

        self.__connect_signals()

        self.tabs = Tabs(self, self.__widget_tree)
        self.image_area = ImageArea(self, self.__widget_tree)

        gtk_refresh()
        self.main_window.set_visible(True)

        self.new_document()

        gtk_refresh()

        self.__check_workdir()

        self.update_scan_buttons_state()

        try:
            self.__widget_tree.get_object("menubarMainWin").set_sensitive(False)
            self.__widget_tree.get_object("toolbarMainWin").set_sensitive(False)
            self.reindex()
            self.tabs.show_doc_list(reversed(self.docsearch.docs))
        finally:
            self.__widget_tree.get_object("menubarMainWin").set_sensitive(True)
            self.__widget_tree.get_object("toolbarMainWin").set_sensitive(True)

    def update_scanner_settings(self):
        """
        Apply the scanner settings from the configuration to the currently used
        scanner
        """
        self.__device.selected_device = self.__config.scanner_devid
        self.__device.selected_resolution = self.__config.scanner_resolution

    def update_scan_buttons_state(self):
        """
        Update buttons states (sensitive or not, tooltips, etc)
        """
        self.__widget_tree.get_object("menuitemScan") \
                .set_sensitive(self.__device.state[0])
        self.__widget_tree.get_object("toolbuttonScan") \
                .set_sensitive(self.__device.state[0])
        self.__widget_tree.get_object("buttonScanPage") \
                .set_sensitive(self.__device.state[0])
        tooltips = gtk.Tooltips()
        tooltips.set_tip(self.__widget_tree.get_object("toolbuttonScan"),
                         self.__device.state[1])
        tooltips.set_tip(self.__widget_tree.get_object("buttonScanPage"),
                         self.__device.state[1])

    def set_progress(self, progress, text):
        """
        Change the progress bar progression and the status bar status

        Arguments:
            progress --- float
            text --- (localized) string
        """
        self.__status_bar.pop(self.__status_context_id)
        self.__status_bar.push(self.__status_context_id, text)
        self.__progress_bar.set_fraction(progress)

    def reindex(self):
        """
        Reload and reindex all the documents
        """
        try:
            self.show_busy_cursor()
            self.tabs.set_result_lists_sensitive(False)
            self.set_progress(0.0, "")
            self.docsearch = DocSearch(self.__config.workdir,
                                       self.cb_progress)
        finally:
            self.tabs.set_result_lists_sensitive(True)
            self.set_progress(0.0, "")
            self.show_normal_cursor()

    def show_busy_cursor(self):
        """
        Turn the mouse cursor into one indicating that the program is currently
        busy.
        """
        watch = gtk.gdk.Cursor(gtk.gdk.WATCH)
        self.main_window.window.set_cursor(watch)
        self.image_area.show_busy_cursor()
        gtk_refresh()

    def show_normal_cursor(self):
        """
        Make sure the mouse cursor if the default one.
        """
        self.main_window.window.set_cursor(None)
        self.image_area.show_normal_cursor()

    def __show_settings(self):
        """
        Make the settings dialog appear
        """
        self.show_busy_cursor()
        gtk_refresh()
        try:
            SettingsWindow(self, self.__config, self.__device)
        finally:
            self.show_normal_cursor()

    def __check_workdir(self):
        """
        Check that the current work dir (see config.PaperworkConfig) exists. If
        not, open the settings dialog.
        """
        try:
            os.stat(self.__config.workdir)
            return
        except OSError, exc:
            print ("Unable to stat dir '%s': %s --> mkdir"
                   % (self.__config.workdir, exc))

        try:
            os.mkdir(self.__config.workdir, 0755)
            return
        except OSError, exc:
            print ("Unable to mkdir '%s': %s --> opening settings window"
                  % (self.__config.workdir, exc))

        self.__show_settings()
        return

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

    def __set_current_page(self, page):
        """
        Display the specified page
        """
        self.tabs.set_page_changers_sensitive(False)
        try:
            assert(page != None)
            self.__page = page
            self.__page_scaled = True

            print "Showing page '%s'" % (page)

            self.image_area.show_page(page)
            self.tabs.select_page(page)
            try:
                self.__show_page_txt(page)
            except IOError, exc:
                print "Unable to show text for doc '%s': %s" % (page, exc)
                self.__page_txt.get_buffer().set_text("")
        finally:
            self.tabs.set_page_changers_sensitive(True)

    def __get_current_page(self):
        return self.__page

    page = property(__get_current_page, __set_current_page)

    def __refresh_page(self):
        """
        Refresh the display of the current page.
        """
        print "Refreshing main window"
        self.image_area.show_page(self.__page)
        self.__reset_page_vpaned()

    def cb_progress(self, progression, total, step, doc=None):
        """
        Update the main progress bar
        """
        txt = None
        if step == ScannedPage.SCAN_STEP_SCAN:
            txt = _('Scanning ...')
        elif step == ScannedPage.SCAN_STEP_OCR:
            txt = _('Reading ...')
        elif step == DocSearch.INDEX_STEP_READING:
            txt = _('Reading ...')
        elif step == DocSearch.INDEX_STEP_SORTING:
            txt = _('Sorting ...')
        elif step == DocSearch.LABEL_STEP_UPDATING:
            txt = _('Updating label ...')
        elif step == DocSearch.LABEL_STEP_DESTROYING:
            txt = _('Removing label ...')
        else:
            assert(False)  # unknown progression type
            txt = ""
        if doc != None:
            txt += (" (%s)" % (doc.name))
        self.set_progress(float(progression) / total, txt)
        gtk_refresh()

    def scan_next_page(self):
        """
        Scan a new page and append it to the current document
        """
        self.__check_workdir()

        self.tabs.show_tab(self.tabs.TAB_PAGES)

        self.show_busy_cursor()
        try:
            self.doc.scan_next_page(self.__device,
                                    self.__config.ocrlang,
                                    self.__config.scanner_calibration,
                                    self.cb_progress)
            page = self.doc.pages[self.doc.nb_pages - 1]
            self.docsearch.index_page(page)
            self.tabs.refresh_page_list()
            self.page = page
            # in case a document was freshly created, we have to update the
            # document list as well
            self.tabs.refresh_doc_list()
            self.__reset_page_vpaned()
        finally:
            self.set_progress(0.0, "")
            self.show_normal_cursor()

    def __scan_next_page_cb(self, objsrc=None):
        self.scan_next_page()

    def __ask_confirmation(self):
        """
        Ask the user "Are you sure ?"

        Returns:
            True --- if they are
            False --- if they aren't
        """
        confirm = gtk.MessageDialog(parent=self.main_window,
                flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                type=gtk.MESSAGE_WARNING,
                buttons=gtk.BUTTONS_YES_NO,
                message_format=_('Are you sure ?'))
        response = confirm.run()
        confirm.destroy()
        if response != gtk.RESPONSE_YES:
            print "User cancelled"
            return False
        return True

    def must_show_all_boxes(self):
        return self.__show_all_boxes.get_active()

    def destroy_doc(self, doc):
        """
        Ask for confirmation and then delete the document being viewed.
        """
        if not self.__ask_confirmation():
            return
        must_start_new_doc = (self.doc == doc)
        print "Deleting ..."
        doc.destroy()
        if must_start_new_doc:
            self.new_document()
        print "Deleted"
        self.reindex()

    def edit_label(self, label):
        """
        Open the edit dialog on the given label, and then apply changes (if
        the user validates their changes)
        """
        assert(label != None)
        new_label = copy(label)
        editor = LabelEditor(new_label)
        if not editor.edit(self.main_window):
            print "Label edition cancelled"
            return
        print "Label edited. Applying changes"
        try:
            self.show_busy_cursor()
            self.tabs.set_result_lists_sensitive(False)
            self.set_progress(0.0, "")
            self.docsearch.update_label(label, new_label, self.cb_progress)
            print "Label updated"
            self.reindex()
        finally:
            self.set_progress(0.0, "")
            self.tabs.set_result_lists_sensitive(True)
            self.show_normal_cursor()

    def destroy_label(self, label):
        """
        Delete the given label
        """
        assert(label != None)
        if not self.__ask_confirmation():
            return
        try:
            self.show_busy_cursor()
            self.tabs.set_result_lists_sensitive(False)
            self.set_progress(0.0, "")
            self.docsearch.destroy_label(label, self.cb_progress)
            print "Label destroyed"
            self.reindex()
        finally:
            self.set_progress(0.0, "")
            self.tabs.set_result_lists_sensitive(True)
            self.show_normal_cursor()

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

        print_op.set_n_pages(self.doc.nb_pages)
        print_op.set_current_page(self.page.page_nb)
        print_op.set_use_full_page(True)
        print_op.set_job_name(str(self.doc))
        print_op.set_export_filename(str(self.doc) + ".pdf")
        print_op.set_allow_async(True)
        print_op.connect("draw-page", self.doc.print_page_cb)
        print_op.run(gtk.PRINT_OPERATION_ACTION_PRINT_DIALOG,
                     self.main_window)

    def __redo_ocr_on_all_cb(self, src=None):
        """
        Redo the OCR all *all* the documents
        """
        msg = _('This may take a very long time\nAre you sure ?')
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
            self.show_busy_cursor()
            self.set_progress(0.0, "")
            self.docsearch.redo_ocr(self.cb_progress,
                                    self.__config.ocrlang)
        finally:
            self.set_progress(0.0, "")
            self.show_normal_cursor()
        self.reindex()

    def __redo_ocr_on_current_cb(self, src=None):
        """
        Redo the OCR all *all* the documents
        """
        try:
            self.show_busy_cursor()
            self.set_progress(0.0, "")
            self.doc.redo_ocr(self.__config.ocrlang, self.cb_progress)
        finally:
            self.set_progress(0.0, "")
            self.show_normal_cursor()
        self.reindex()

    def __on_resize_cb(self, window=None, allocation=None):
        """
        Called each time the main window is resized
        """
        if self.__win_size != allocation:
            print "Main window resized"
            self.__win_size = allocation
            self.__reset_page_vpaned()

    def __show_about_dialog_cb(self, objsrc=None):
        """
        Create and show the about dialog.
        """
        about = AboutDialog(self.main_window)
        about.show()

    def destroy_page(self, page):
        """
        Destroy/delete a page
        """
        if not self.__ask_confirmation():
            return
        page.destroy()
        self.reindex()
        self.tabs.refresh_page_list()
        if (self.page == page):
            self.page = None

    def __connect_signals(self):
        """
        Connect all the main window signals to their callbacks
        """
        self.main_window.connect("destroy", lambda x: self.__destroy())
        self.main_window.connect("size-allocate", self.__on_resize_cb)
        self.__widget_tree.get_object("menuitemNew").connect("activate",
                self.__new_document_cb)
        self.__widget_tree.get_object("toolbuttonNew").connect("clicked",
                self.__new_document_cb)
        self.__widget_tree.get_object("toolbuttonQuit").connect("clicked",
                lambda x: self.__destroy())
        self.__widget_tree.get_object("menuitemScan").connect("activate",
                self.__scan_next_page_cb)
        self.__widget_tree.get_object("toolbuttonScan").connect("clicked",
                self.__scan_next_page_cb)
        self.__widget_tree.get_object("toolbuttonPrint").connect("clicked",
                self.__print_doc_cb)
        self.__widget_tree.get_object("menuitemPrint").connect("activate",
                self.__print_doc_cb)
        self.__widget_tree.get_object("menuitemQuit").connect("activate",
                lambda x: self.__destroy())
        self.__widget_tree.get_object("menuitemAbout").connect("activate",
                self.__show_about_dialog_cb)
        self.__widget_tree.get_object("menuitemSettings").connect("activate",
                lambda x: self.__show_settings())
        self.__widget_tree.get_object("menuitemReOcrAll").connect("activate",
                self.__redo_ocr_on_all_cb)
        self.__widget_tree.get_object("menuitemReOcr").connect("activate",
                self.__redo_ocr_on_current_cb)
        self.__widget_tree.get_object("menuitemReindexAll").connect("activate",
                lambda x: self.reindex())
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
        pass

    def __show_doc(self, doc=None):
        """
        Arguments:
            doc --- doc.ScannedDoc (see docsearch.DocSearch.docs[])
        """
        if doc != None:
            self.__doc = doc
        else:
            assert(self.__doc)

        self.main_window.set_title(self.__doc.name + " - " + self.WIN_TITLE)
        self.tabs.refresh_page_list()
        assert(self.__doc.pages[0] != None)
        print "Showing first page of the doc"
        self.page = self.__doc.pages[0]
        self.tabs.refresh_label_list()

    def __set_current_doc(self, doc):
        """
        Display the specified document
        """
        self.__show_doc(doc)
        self.__reset_page_vpaned()

    def __get_current_doc(self):
        return self.__doc

    doc = property(__get_current_doc, __set_current_doc)

    def new_document(self):
        """
        Start the edition of the new document.
        """
        self.tabs.show_tab(self.tabs.TAB_PAGES)
        self.__show_doc(ScannedDoc(self.__config.workdir))  # new document

    def __new_document_cb(self, objsrc=None):
        """
        Alias for new_document()
        """
        self.new_document()
