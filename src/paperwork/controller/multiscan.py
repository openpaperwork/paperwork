"""
Dialog to scan many pages and document at once
"""

import gettext
import gtk

from paperwork.model.doc import ScannedDoc
from paperwork.model.page import ScannedPage
from paperwork.util import gtk_refresh
from paperwork.util import load_uifile

_ = gettext.gettext

class MultiscanDialog(object):
    def __init__(self, mainwindow, config, device):
        self.__mainwindow = mainwindow
        self.__config = config
        self.__device = device
        self.__widget_tree = load_uifile("multiscan.glade")

        # scan_list: array of integers (nb_pages, progression, current_op)
        self.__scan_list = [ (1, 0, None) ]
        self.__running = False
        # current_scan: (current_doc_idx, current_page, total_pages)
        self.__current_scan = None

        self.__multiscan_dialog = \
                self.__widget_tree.get_object("dialogMultiscan")
        self.__scan_list_model = \
                self.__widget_tree.get_object("liststoreScanList")
        self.__scan_list_ui = self.__widget_tree.get_object("treeviewScanList")
        self.__nb_pages_column = \
                self.__widget_tree.get_object("treeviewcolumnNbPages")

        self.__multiscan_dialog.set_transient_for(mainwindow.main_window)

        self.__connect_signals()

        self.__multiscan_dialog.set_visible(True)

    def __reload_scan_list(self):
        self.__scan_list_model.clear()
        for i in range(0, len(self.__scan_list)):
            (nb_pages, progress, current_op) = self.__scan_list[i]
            txt = _("Document %d") % (i+1)
            if (current_op != None):
                txt += " (%s)" % (current_op)
            self.__scan_list_model.append([
                txt,
                nb_pages,
                progress,
                i # line number
            ])

    def __destroy_cb(self, widget=None):
        self.__multiscan_dialog.destroy()

    def __cancel_cb(self, widget=None):
        self.__running = False
        if self.__current_scan == None:
            self.__destroy_cb()

    def __modify_doc_cb(self, widget=None):
        selection_path = self.__scan_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No doc selected"
        line = selection_path[0].get_value(selection_path[1], 3)
        self.__scan_list_ui.set_cursor(line,
                                       self.__nb_pages_column,
                                       start_editing=True)

    def __add_doc_cb(self, widget=None):
        self.__scan_list.append((1, 0, None))
        self.__reload_scan_list()

    def __remove_doc_cb(self, widget=None):
        selection_path = self.__scan_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No doc selected"
            return True
        line = selection_path[0].get_value(selection_path[1], 3)
        self.__scan_list.remove(self.__scan_list[line])
        self.__reload_scan_list()
        return True

    def __nb_pages_edited_cb(self, cellrenderer, path, new_text):
        selection_path = self.__scan_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No doc selected"
            return True

        line = selection_path[0].get_value(selection_path[1], 3)
        val = -1
        try:
            val = int(new_text)
        except ValueError:
            pass
        if val < 0:
            print "Invalid value: %s" % (new_text)
            return False

        self.__scan_list[line] = (val, 0, None)
        self.__reload_scan_list()
        return True

    def __show_busy_cursor(self):
        watch = gtk.gdk.Cursor(gtk.gdk.WATCH)
        self.__multiscan_dialog.window.set_cursor(watch)
        gtk_refresh()

    def __show_normal_cursor(self):
        self.__multiscan_dialog.window.set_cursor(None)

    def __set_widgets_sensitive(self, sensitive=True):
        # all but the cancel button
        self.__widget_tree.get_object("buttonEditDoc").set_sensitive(sensitive)
        self.__widget_tree.get_object("buttonRemoveDoc").set_sensitive(
            sensitive)
        self.__widget_tree.get_object("buttonAddDoc").set_sensitive(sensitive)
        self.__widget_tree.get_object("buttonOk").set_sensitive(sensitive)

    def __scan_progress_cb(self, progression, total, step=None, doc=None):
        """
        Update the scan list to show the progression
        """
        (doc_idx, page_idx, total_pages) = self.__current_scan

        page_progress = 100 / total_pages
        progress = page_idx * page_progress
        if step == ScannedPage.SCAN_STEP_SCAN:
            txt = _('Scanning ...')
        elif step == ScannedPage.SCAN_STEP_OCR:
            txt = _('Reading ...')
            progress += page_progress / 2
        else:
            txt = None

        self.__scan_list[doc_idx] = (total_pages, progress, txt)
        self.__reload_scan_list()
        gtk_refresh()

    def __scan_all_cb(self, widget=None):
        total = 0
        self.__running = True
        try:
            self.__show_busy_cursor()
            self.__set_widgets_sensitive(False)
            scan_src = self.__device.open(multiscan=True)
            try:
                for doc_idx in range(0, len(self.__scan_list)):
                    nb_pages = self.__scan_list[doc_idx][0]
                    doc = ScannedDoc(self.__config.workdir) # new document
                    for page_idx in range(0, nb_pages):
                        if not self.__running:
                            raise StopIteration()
                        self.__current_scan = (doc_idx, page_idx, nb_pages)
                        doc.scan_single_page(scan_src,
                                             self.__config.ocrlang,
                                             self.__config.scanner_calibration,
                                             callback=self.__scan_progress_cb)
                        total += 1
                    self.__scan_list[doc_idx] = (nb_pages, 100, None)
                    self.__reload_scan_list()
                    gtk_refresh()
            finally:
                scan_src.close()
        except StopIteration:
            msg = _("Less pages than expected have been scanned"
                    " (got %d pages)") % (total)
            dialog = gtk.MessageDialog(flags=gtk.DIALOG_MODAL,
                                       type=gtk.MESSAGE_WARNING,
                                       buttons=gtk.BUTTONS_OK,
                                       message_format=msg)
            dialog.run()
            dialog.destroy()
        finally:
            self.__set_widgets_sensitive(True)
            self.__show_normal_cursor()
        self.__multiscan_dialog.destroy()
        self.__mainwindow.reindex()

    def __connect_signals(self):
        self.__multiscan_dialog.connect("destroy", self.__destroy_cb)
        self.__widget_tree.get_object("buttonEditDoc").connect(
                "clicked", self.__modify_doc_cb)
        self.__widget_tree.get_object("buttonRemoveDoc").connect(
                "clicked", self.__remove_doc_cb)
        self.__widget_tree.get_object("buttonAddDoc").connect(
                "clicked", self.__add_doc_cb)
        self.__widget_tree.get_object("cellrenderertextNbPages").connect(
                "edited", self.__nb_pages_edited_cb)
        self.__widget_tree.get_object("buttonOk").connect(
                "clicked", self.__scan_all_cb)
        self.__widget_tree.get_object("buttonCancel").connect(
                "clicked", self.__cancel_cb)
