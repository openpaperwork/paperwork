from copy import copy
import os
import sys
import threading
import time

import Image
import ImageColor
import ImageDraw
import gtk
import gettext
import gobject

import pyinsane.rawapi

from paperwork.controller.aboutdialog import AboutDialog
from paperwork.controller.actions import SimpleAction
from paperwork.controller.multiscan import MultiscanDialog
from paperwork.controller.settingswindow import SettingsWindow
from paperwork.controller.workers import Worker
from paperwork.controller.workers import WorkerProgressUpdater
from paperwork.model import docimport
from paperwork.model.docsearch import DocSearch
from paperwork.model.docsearch import DummyDocSearch
from paperwork.model.img.doc import ImgDoc
from paperwork.model.img.page import ImgPage
from paperwork.model.labels import LabelEditor
from paperwork.util import ask_confirmation
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile
from paperwork.util import popup_no_scanner_found

_ = gettext.gettext


def check_workdir(config):
    """
    Check that the current work dir (see config.PaperworkConfig) exists. If
    not, open the settings dialog.
    """
    try:
        os.stat(config.workdir)
        return
    except OSError, exc:
        print ("Unable to stat dir '%s': %s --> mkdir"
               % (config.workdir, exc))

    os.mkdir(config.workdir, 0755)


class WorkerDocIndexer(Worker):
    """
    Reindex all the documents
    """

    __gsignals__ = {
        'indexation-start' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'indexation-progression' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                                    (gobject.TYPE_FLOAT, gobject.TYPE_STRING)),
        'indexation-end' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    can_interrupt = True

    def __init__(self, main_window, config):
        Worker.__init__(self, "Document reindexation")
        self.__main_win = main_window
        self.__config = config

    def __progress_cb(self, progression, total, step, doc=None):
        """
        Update the main progress bar
        """
        txt = None
        if step == DocSearch.INDEX_STEP_READING:
            txt = _('Reading ...')
        elif step == DocSearch.INDEX_STEP_SORTING:
            txt = _('Sorting ...')
        else:
            assert()  # unknown progression type
            txt = ""
        if doc != None:
            txt += (" (%s)" % (doc.name))
        self.emit('indexation-progression', float(progression) / total, txt)
        if not self.can_run:
            raise StopIteration()

    def do(self):
        self.emit('indexation-start')
        try:
            docsearch = DocSearch(self.__config.workdir, self.__progress_cb)
            self.__main_win.docsearch = docsearch
        except StopIteration:
            print "Indexation interrupted"
        self.emit('indexation-end')

gobject.type_register(WorkerDocIndexer)


class WorkerThumbnailer(Worker):
    """
    Generate thumbnails
    """

    __gsignals__ = {
        'thumbnailing-start' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'thumbnailing-page-done':
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
             (gobject.TYPE_INT, gobject.TYPE_PYOBJECT)),
        'thumbnailing-end' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    can_interrupt = True

    def __init__(self, main_window):
        Worker.__init__(self, "Thumbnailing")
        self.__main_win = main_window

    def do(self):
        self.emit('thumbnailing-start')
        # give some time to the GUI to breath
        time.sleep(0.3)
        for page_idx in range(0, self.__main_win.doc.nb_pages):
            page = self.__main_win.doc.pages[page_idx]
            img = page.get_thumbnail(150)
            pixbuf = image2pixbuf(img)
            if not self.can_run:
                return
            self.emit('thumbnailing-page-done', page_idx, pixbuf)
            # give some time to the GUI to breath
            time.sleep(0.3)
        self.emit('thumbnailing-end')


gobject.type_register(WorkerThumbnailer)


class WorkerImgBuilder(Worker):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'img-building-start' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'img-building-result-pixbuf' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
             (gobject.TYPE_FLOAT, gobject.TYPE_PYOBJECT, )),
        'img-building-result-stock' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
             (gobject.TYPE_STRING, )),
    }

    # even if it's not true, this process is not really long, so it doesn't
    # really matter
    can_interrupt = True

    def __init__(self, main_window):
        Worker.__init__(self, "Building page image")
        self.__main_win = main_window

    def __get_img_area_width(self):
        width = self.__main_win.img['scrollbar'].get_allocation().width
        # TODO(JFlesch): This is not a safe assumption:
        width -= 30
        return width

    def __get_zoom_factor(self, original_pixbuf):
        el_idx = self.__main_win.lists['zoom_levels'][0].get_active()
        el_iter = self.__main_win.lists['zoom_levels'][1].get_iter(el_idx)
        factor = self.__main_win.lists['zoom_levels'][1].get_value(el_iter, 1)
        if factor != 0.0:
            return factor
        wanted_width = self.__get_img_area_width()
        return float(wanted_width) / original_pixbuf.get_width()

    def do(self):
        self.emit('img-building-start')

        if self.__main_win.page == None:
            self.emit('img-building-result-stock', gtk.STOCK_MISSING_IMAGE)
            return

        try:
            img = self.__main_win.page.img

            pixbuf = image2pixbuf(img)

            factor = self.__get_zoom_factor(pixbuf)
            print "Zoom: %f" % (factor)

            wanted_width = int(factor * pixbuf.get_width())
            wanted_height = int(factor * pixbuf.get_height())
            pixbuf = pixbuf.scale_simple(wanted_width, wanted_height,
                                         gtk.gdk.INTERP_BILINEAR)

            self.emit('img-building-result-pixbuf', factor, pixbuf)
        except Exception, exc:
            self.emit('img-building-result-stock', gtk.STOCK_DIALOG_ERROR)
            raise exc


gobject.type_register(WorkerImgBuilder)


class WorkerLabelUpdater(Worker):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'label-updating-start' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'label-updating-doc-updated' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
             (gobject.TYPE_FLOAT, gobject.TYPE_STRING)),
        'label-updating-end' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    can_interrupt = False

    def __init__(self, main_window):
        Worker.__init__(self, "Updating label")
        self.__main_win = main_window

    def __progress_cb(self, progression, total, step, doc):
        self.emit('label-updating-doc-updated', float(progression) / total,
                  doc.name)

    def do(self, old_label, new_label):
        self.emit('label-updating-start')
        try:
            self.__main_win.docsearch.update_label(old_label, new_label,
                                                   self.__progress_cb)
        finally:
            self.emit('label-updating-end')


gobject.type_register(WorkerLabelUpdater)


class WorkerLabelDeleter(Worker):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'label-deletion-start' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'label-deletion-doc-updated' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
             (gobject.TYPE_FLOAT, gobject.TYPE_STRING)),
        'label-deletion-end' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    can_interrupt = False

    def __init__(self, main_window):
        Worker.__init__(self, "Removing label")
        self.__main_win = main_window

    def __progress_cb(self, progression, total, step, doc):
        self.emit('label-deletion-doc-updated', float(progression) / total,
                  doc.name)

    def do(self, label):
        self.emit('label-deletion-start')
        try:
            self.__main_win.docsearch.destroy_label(label, self.__progress_cb)
        finally:
            self.emit('label-deletion-end')


gobject.type_register(WorkerLabelDeleter)


class WorkerOCRRedoer(Worker):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'redo-ocr-start' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'redo-ocr-doc-updated' :
            (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
             (gobject.TYPE_FLOAT, gobject.TYPE_STRING)),
        'redo-ocr-end' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    can_interrupt = False

    def __init__(self, main_window, config):
        Worker.__init__(self, "Redoing OCR")
        self.__main_win = main_window
        self.__config = config

    def __progress_cb(self, progression, total, step, doc):
        self.emit('redo-ocr-doc-updated', float(progression) / total,
                  doc.name)

    def do(self, doc_target):
        self.emit('redo-ocr-start')
        try:
            doc_target.redo_ocr(self.__config.ocrlang, self.__progress_cb)
        finally:
            self.emit('redo-ocr-end')


gobject.type_register(WorkerOCRRedoer)


class WorkerSingleScan(Worker):
    __gsignals__ = {
        'single-scan-start' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'single-scan-ocr' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'single-scan-done' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                              (gobject.TYPE_PYOBJECT,) # ImgPage
                             ),
    }

    can_interrupt = True

    def __init__(self, main_window, config):
        Worker.__init__(self, "Scanning page")
        self.__main_win = main_window
        self.__config = config
        self.__ocr_running = False

    def __scan_progress_cb(self, progression, total, step, doc=None):
        if not self.can_run:
            raise Exception("Interrupted by the user")
        if (step == ImgPage.SCAN_STEP_OCR) and (not self.__ocr_running):
            self.emit('single-scan-ocr')
            self.__ocr_running = True

    def do(self, doc):
        self.emit('single-scan-start')

        self.__ocr_running = False
        try:
            scanner = self.__config.get_scanner_inst()
        except Exception:
            print "No scanner found !"
            gobject.idle_add(popup_no_scanner_found, self.__main_win.window)
            self.emit('single-scan-done', None)
            raise
        try:
            scanner.options['source'].value = "Auto"
        except pyinsane.rawapi.SaneException, exc:
            print ("Warning: Unable to set scanner source to 'Auto': %s" %
                   (str(exc)))
        scan_src = scanner.scan(multiple=False)
        doc.scan_single_page(scan_src, scanner.options['resolution'].value,
                             self.__config.ocrlang,
                             self.__config.scanner_calibration,
                             self.__scan_progress_cb)
        page = doc.pages[doc.nb_pages - 1]
        self.__main_win.docsearch.index_page(page)

        self.emit('single-scan-done', page)


gobject.type_register(WorkerSingleScan)


class ActionNewDocument(SimpleAction):
    """
    Starts a new document.
    """
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "New document")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        self.__main_win.workers['thumbnailer'].stop()
        self.__main_win.workers['img_builder'].stop()
        doc = ImgDoc(self.__config.workdir)
        self.__main_win.doc = doc
        for widget in self.__main_win.need_doc_widgets:
            widget.set_sensitive(False)
        for widget in self.__main_win.doc_edit_widgets:
            widget.set_sensitive(doc.can_edit)
        self.__main_win.page = None
        self.__main_win.refresh_page_list()
        self.__main_win.refresh_label_list()
        self.__main_win.workers['img_builder'].start()


class ActionOpenSelectedDocument(SimpleAction):
    """
    Starts a new document.
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open selected document")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        (model, selection_iter) = \
                self.__main_win.lists['matches'][0].get_selection().get_selected()
        if selection_iter == None:
            print "No document selected. Can't open"
            return
        doc = model.get_value(selection_iter, 1)

        print "Showing doc %s" % doc
        self.__main_win.show_doc(doc)

class ActionStartSimpleWorker(SimpleAction):
    """
    Start a threaded job
    """
    def __init__(self, worker):
        SimpleAction.__init__(self, str(worker))
        self.__worker = worker

    def do(self):
        SimpleAction.do(self)
        self.__worker.start()


class ActionUpdateSearchResults(SimpleAction):
    """
    Update search results
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Update search results")
        self.__main_win = main_window
    
    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_doc_list()
        self.__main_win.refresh_highlighted_words()

    def on_icon_press_cb(self, entry, iconpos=None, event=None):
        entry.set_text("")


class ActionPageSelected(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, 
                "Show a page (selected from the thumbnail list)")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        selection_path = self.__main_win.lists['pages'][0].get_selected_items()
        if len(selection_path) <= 0:
            return None
        # TODO(Jflesch): We should get the page number from the list content,
        # not from the position of the element in the list
        page_idx = selection_path[0][0]
        page = self.__main_win.doc.pages[page_idx]
        self.__main_win.show_page(page)
        # TODO(Jflesch): Move the vertical scrollbar of the page list
        # up to the selected value


class ActionMovePageIndex(SimpleAction):
    def __init__(self, main_window, offset):
        txt = "previous"
        if offset > 0:
            txt = "next"
        SimpleAction.__init__(self, ("Show the %s page" % (txt)))
        self.offset = offset
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        page_idx = self.__main_win.page.page_nb
        page_idx += self.offset
        if page_idx < 0 or page_idx >= self.__main_win.doc.nb_pages:
            return
        page = self.__main_win.doc.pages[page_idx]
        self.__main_win.show_page(page)
        # TODO(Jflesch): Move the vertical scrollbar of the page list
        # up to the selected value


class ActionOpenPageNb(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Show a page (selected on its number)")
        self.__main_win = main_window

    def entry_changed(self, entry):
        pass

    def do(self):
        SimpleAction.do(self)
        page_nb = self.__main_win.indicators['current_page'].get_text()
        page_nb = int(page_nb) - 1
        if page_nb < 0 or page_nb > self.__main_win.doc.nb_pages:
            return
        page = self.__main_win.doc.pages[page_nb]
        self.__main_win.show_page(page)


class ActionRebuildPage(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Refresh current page")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.workers['img_builder'].stop()
        self.__main_win.workers['img_builder'].start()


class ActionLabelSelected(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Label selected")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        for widget in self.__main_win.need_label_widgets:
            widget.set_sensitive(True)


class ActionToggleLabel(object):
    def __init__(self, main_window):
        self.__main_win = main_window

    def toggle_cb(self, renderer, objpath):
        label = self.__main_win.lists['labels'][1][objpath][2]
        if not label in self.__main_win.doc.labels:
            print ("Action: Adding label '%s' on document '%s'"
                   % (str(label), str(self.__main_win.doc)))
            self.__main_win.doc.add_label(label)
        else:
            print ("Action: Removing label '%s' on document '%s'"
                   % (str(label), str(self.__main_win.doc)))
            self.__main_win.doc.remove_label(label)
        self.__main_win.refresh_label_list()
        self.__main_win.refresh_doc_list()
        # TODO(Jflesch): Update keyword index

    def connect(self, cellrenderers):
        for cellrenderer in cellrenderers:
            cellrenderer.connect('toggled', self.toggle_cb)


class ActionCreateLabel(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Creating label")
        self.__main_win = main_window

    def do(self):
        labeleditor = LabelEditor()
        if labeleditor.edit(self.__main_win.window):
            print "Adding label %s to doc %s" % (str(labeleditor.label),
                                                 str(self.__main_win.doc))
            self.__main_win.doc.add_label(labeleditor.label)
            self.__main_win.docsearch.add_label(labeleditor.label,
                                                self.__main_win.doc)
        self.__main_win.refresh_label_list()


class ActionEditLabel(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Editing label")
        self.__main_win = main_window

    def do(self):
        if self.__main_win.workers['label_updater'].is_running:
            return

        selection_path = self.__main_win.lists['labels'][0] \
                .get_selection().get_selected()
        if selection_path[1] == None:
            print "No label selected"
            return True
        label = selection_path[0].get_value(selection_path[1], 2)

        new_label = copy(label)
        editor = LabelEditor(new_label)
        if not editor.edit(self.__main_win.window):
            print "Label edition cancelled"
            return
        print "Label edited. Applying changes"
        if self.__main_win.workers['label_updater'].is_running:
            return
        self.__main_win.workers['label_updater'].start(old_label=label,
                                                       new_label=new_label)


class ActionDeleteLabel(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Deleting label")
        self.__main_win = main_window

    def do(self):
        if self.__main_win.workers['label_deleter'].is_running:
            return

        if not ask_confirmation(self.__main_win.window):
            return

        selection_path = self.__main_win.lists['labels'][0] \
                .get_selection().get_selected()
        if selection_path[1] == None:
            print "No label selected"
            return True
        label = selection_path[0].get_value(selection_path[1], 2)

        if self.__main_win.workers['label_deleter'].is_running:
            return
        self.__main_win.workers['label_deleter'].start(label=label)


class ActionOpenDocDir(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open doc dir")
        self.__main_win = main_window

    def do(self):
        os.system('xdg-open "%s"' % (self.__main_win.doc.path))


class ActionPrintDoc(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open print dialog")
        self.__main_win = main_window

    def do(self):
        print_settings = gtk.PrintSettings()
        # By default, print context are using 72 dpi, but print_draw_page
        # will change it to 300 dpi --> we have to tell PrintOperation to scale
        print_settings.set_scale(100.0 * (72.0 / ImgPage.PRINT_RESOLUTION))

        print_op = gtk.PrintOperation()
        print_op.set_print_settings(print_settings)
        print_op.set_n_pages(self.__main_win.doc.nb_pages)
        print_op.set_current_page(self.__main_win.page.page_nb)
        print_op.set_use_full_page(True)
        print_op.set_job_name(str(self.__main_win.doc))
        print_op.set_export_filename(str(self.__main_win.doc) + ".pdf")
        print_op.set_allow_async(True)
        print_op.connect("draw-page", self.__main_win.doc.print_page_cb)
        print_op.run(gtk.PRINT_OPERATION_ACTION_PRINT_DIALOG,
                     self.__main_win.window)


class ActionOpenSettings(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Open settings dialog")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        sw = SettingsWindow(self.__main_win.window, self.__config)
        sw.connect("need-reindex", self.__reindex_cb)

    def __reindex_cb(self, settings_window):
        self.__main_win.workers['reindex'].start()


class ActionSingleScan(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Scan a single page")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        check_workdir(self.__config)
        self.__main_win.workers['single_scan'].start(
                doc=self.__main_win.doc)


class ActionMultiScan(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Scan multiples pages")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        check_workdir(self.__config)
        ms = MultiscanDialog(self.__main_win, self.__config)
        ms.connect("need-reindex", self.__reindex_cb)

    def __reindex_cb(self, settings_window):
        self.__main_win.workers['reindex'].start()


class ActionImport(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Import file(s)")
        self.__main_win = main_window
        self.__config = config

    def __select_file(self):
        widget_tree = load_uifile("import.glade")
        dialog = widget_tree.get_object("filechooserdialog")
        dialog.set_local_only(False)
        dialog.set_select_multiple(False)
        dialog.set_current_folder(self.__config.workdir)

        response = dialog.run()
        if response != 0:
            print "Import: Canceled by user"
            dialog.destroy()
            return None
        file_uri = dialog.get_uri()
        dialog.destroy()
        print "Import: %s" % file_uri
        return file_uri


    def do(self):
        check_workdir(self.__config)

        file_uri = self.__select_file()
        if file_uri == None:
            return

        importers = docimport.get_possible_importers(file_uri,
                                                     self.__main_win.doc)
        if len(importers) <= 0:
            msg = (_("Don't know how to import '%s'. Sorry.") %
                   (os.path.basename(file_uri)))
            dialog = \
                gtk.MessageDialog(parent=self.__main_win.window,
                                  flags=(gtk.DIALOG_MODAL
                                         |gtk.DIALOG_DESTROY_WITH_PARENT),
                                  type=gtk.MESSAGE_ERROR,
                                  buttons=gtk.BUTTONS_OK,
                                  message_format=msg)
            dialog.run()
            dialog.destroy()
            return

        # TODO(Jflesch): Handle multiple importers !
        assert(len(importers) == 1)
        doc = importers[0].import_doc(file_uri, self.__config,
                                      self.__main_win.docsearch,
                                      self.__main_win.doc)
        self.__main_win.show_doc(doc)
        self.__main_win.refresh_doc_list()


class ActionDeleteDoc(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Delete document")
        self.__main_win = main_window

    def do(self):
        """
        Ask for confirmation and then delete the document being viewed.
        """
        if not ask_confirmation(self.__main_win.window):
            return
        print "Deleting ..."
        self.__main_win.doc.destroy()
        print "Deleted"
        self.__main_win.actions['new_doc'][1].do()
        self.__main_win.workers['reindex'].start()


class ActionDeletePage(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Delete page")
        self.__main_win = main_window

    def do(self):
        """
        Ask for confirmation and then delete the page being viewed.
        """
        if not ask_confirmation(self.__main_win.window):
            return
        print "Deleting ..."
        self.__main_win.page.destroy()
        print "Deleted"
        self.__main_win.workers['thumbnailer'].stop()
        self.__main_win.workers['img_builder'].stop()
        self.__main_win.page = None
        for widget in self.__main_win.need_page_widgets:
            widget.set_sensitive(False)
        self.__main_win.refresh_page_list()
        self.__main_win.refresh_label_list()
        self.__main_win.workers['img_builder'].start()
        self.__main_win.workers['thumbnailer'].start()
        self.__main_win.workers['reindex'].start()


class ActionRedoDocOCR(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Redoing doc ocr")
        self.__main_win = main_window

    def do(self):
        if not ask_confirmation(self.__main_win.window):
            return

        if self.__main_win.workers['ocr_redoer'].is_running:
            return

        self.__main_win.workers['ocr_redoer'].start(doc_target=self.__main_win.doc)


class ActionRedoAllOCR(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Redoing doc ocr")
        self.__main_win = main_window

    def do(self):
        if not ask_confirmation(self.__main_win.window):
            return

        if self.__main_win.workers['ocr_redoer'].is_running:
            return

        self.__main_win.workers['ocr_redoer'].start(doc_target=self.__main_win.docsearch)


class ActionAbout(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Opening about dialog")
        self.__main_win = main_window

    def do(self):
        about = AboutDialog(self.__main_win.window)
        about.show()
        

class ActionQuit(SimpleAction):
    """
    Quit
    """
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Quit")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        self.__main_win.window.destroy()

    def on_window_close_cb(self, window):
        self.do()


class ActionRealQuit(SimpleAction):
    """
    Quit
    """
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Quit (real)")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)

        for worker in self.__main_win.workers.values():
            worker.stop()

        self.__config.write()
        gtk.main_quit()

    def on_window_close_cb(self, window):
        self.do()


class MainWindow(object):
    def __init__(self, config):
        img = Image.new("RGB", (150, 200), ImageColor.getrgb("#EEEEEE"))
        # TODO(Jflesch): Find a better default thumbnail
        self.default_thumbnail = image2pixbuf(img)
        del img

        widget_tree = load_uifile("mainwindow.glade")

        self.window = widget_tree.get_object("mainWindow")
        self.__win_size_cache = None

        self.__config = config
        self.__scan_start = 0.0

        self.docsearch = DummyDocSearch()
        self.doc = None
        self.page = None

        self.lists = {
            'suggestions' : (
                widget_tree.get_object("entrySearch"),
                widget_tree.get_object("liststoreSuggestion")
            ),
            'matches' : (
                widget_tree.get_object("treeviewMatch"),
                widget_tree.get_object("liststoreMatch"),
            ),
            'pages' : (
                widget_tree.get_object("iconviewPage"),
                widget_tree.get_object("liststorePage"),
            ),
            'labels' : (
                widget_tree.get_object("treeviewLabel"),
                widget_tree.get_object("liststoreLabel"),
            ),
            'zoom_levels' : (
                widget_tree.get_object("comboboxZoom"),
                widget_tree.get_object("liststoreZoom"),
            ),
        }

        search_completion = gtk.EntryCompletion()
        search_completion.set_model(self.lists['suggestions'][1])
        search_completion.set_text_column(0)
        search_completion.set_match_func(lambda x, y, z: True)
        self.lists['suggestions'][0].set_completion(search_completion)

        self.indicators = {
            'current_page' : widget_tree.get_object("entryPageNb"),
            'total_pages' : widget_tree.get_object("labelTotalPages"),
        }

        self.search_field = widget_tree.get_object("entrySearch")
        self.search_field.set_tooltip_text(
                              (_('Search documents\n')
                               + _('\'!\' can be used as a prefix to')
                               + _(' negate a keyword')))

        self.doc_browsing = {
            'matches' : widget_tree.get_object("treeviewMatch"),
            'pages' : widget_tree.get_object("iconviewPage"),
            'labels' : widget_tree.get_object("treeviewLabel"),
            'search' : self.search_field,
        }

        self.text_area = widget_tree.get_object("textviewPageTxt")
        self.img = {
            "image" : widget_tree.get_object("imagePageImg"),
            "scrollbar" : widget_tree.get_object("scrolledwindowPageImg"),
            "eventbox" : widget_tree.get_object("eventboxImg"),
            "pixbuf" : None,
            "factor" : 1.0,
            "boxes" : {
                "highlighted" : [],
                "all" : [],
                "current" : None,
            }
        }

        self.status = {
            'progress' : widget_tree.get_object("progressbar"),
            'text' : widget_tree.get_object("statusbar"),
        }

        self.popupMenus = {
            'labels' : (
                widget_tree.get_object("treeviewLabel"),
                widget_tree.get_object("popupmenuLabels")
            ),
            'matches' : (
                widget_tree.get_object("treeviewMatch"),
                widget_tree.get_object("popupmenuMatchs")
            ),
            'pages' : (
                widget_tree.get_object("iconviewPage"),
                widget_tree.get_object("popupmenuPages")
            )
        }

        self.vpanels = {
            'txt_img_split' : widget_tree.get_object("vpanedPage")
        }

        self.workers = {
            'reindex' : WorkerDocIndexer(self, config),
            'thumbnailer' : WorkerThumbnailer(self),
            'img_builder' : WorkerImgBuilder(self),
            'label_updater' : WorkerLabelUpdater(self),
            'label_deleter' : WorkerLabelDeleter(self),
            'single_scan' : WorkerSingleScan(self, config),
            'progress_updater' : WorkerProgressUpdater(
                "main window progress bar", self.status['progress']),
            'ocr_redoer' : WorkerOCRRedoer(self, config),
        }

        self.show_all_boxes = \
            widget_tree.get_object("checkmenuitemShowAllBoxes")

        self.actions = {
            'new_doc' : (
                [
                    widget_tree.get_object("menuitemNew"),
                    widget_tree.get_object("toolbuttonNew"),
                ],
                ActionNewDocument(self, config),
            ),
            'open_doc' : (
                [
                    widget_tree.get_object("treeviewMatch"),
                ],
                ActionOpenSelectedDocument(self)
            ),
            'open_page' : (
                [
                    widget_tree.get_object("iconviewPage"),
                ],
                ActionPageSelected(self)
            ),
            'select_label' : (
                [
                    widget_tree.get_object("treeviewLabel"),
                ],
                ActionLabelSelected(self)
            ),
            'single_scan' : (
                [
                    widget_tree.get_object("imagemenuitemScanSingle"),
                    widget_tree.get_object("toolbuttonScan"),
                    widget_tree.get_object("menuitemScanSingle"),
                ],
                ActionSingleScan(self, config)
            ),
            'multi_scan' : (
                [
                    widget_tree.get_object("imagemenuitemScanFeeder"),
                    widget_tree.get_object("menuitemScanFeeder"),
                ],
                ActionMultiScan(self, config)
            ),
            'import' : (
                [
                    widget_tree.get_object("menuitemImport"),
                    widget_tree.get_object("menuitemImport1"),
                ],
                ActionImport(self, config)
            ),
            'print' : (
                [
                    widget_tree.get_object("menuitemPrint"),
                    widget_tree.get_object("toolbuttonPrint"),
                ],
                ActionPrintDoc(self)
            ),
            'open_settings' : (
                [
                    widget_tree.get_object("menuitemSettings"),
                    widget_tree.get_object("toolbuttonSettings"),
                ],
                ActionOpenSettings(self, config)
            ),
            'quit' : (
                [
                    widget_tree.get_object("menuitemQuit"),
                    widget_tree.get_object("toolbuttonQuit"),
                ],
                ActionQuit(self, config),
            ),
            'create_label' : (
                [
                    widget_tree.get_object("buttonAddLabel"),
                    widget_tree.get_object("menuitemAddLabel"),
                ],
                ActionCreateLabel(self),
            ),
            'edit_label' : (
                [
                    widget_tree.get_object("menuitemEditLabel"),
                    widget_tree.get_object("buttonEditLabel"),
                ],
                ActionEditLabel(self),
            ),
            'del_label' : (
                [
                    widget_tree.get_object("menuitemDestroyLabel"),
                    widget_tree.get_object("buttonDelLabel"),
                ],
                ActionDeleteLabel(self),
            ),
            'open_doc_dir' : (
                [
                    widget_tree.get_object("menuitemOpenDocDir"),
                    widget_tree.get_object("toolbuttonOpenDocDir"),
                ],
                ActionOpenDocDir(self),
            ),
            'del_doc' : (
                [
                    widget_tree.get_object("menuitemDestroyDoc2"),
                    widget_tree.get_object("toolbuttonDeleteDoc"),
                ],
                ActionDeleteDoc(self),
            ),
            'del_page' : (
                [
                    widget_tree.get_object("menuitemDestroyPage2"),
                    widget_tree.get_object("buttonDeletePage"),
                ],
                ActionDeletePage(self),
            ),
            'prev_page' : (
                [
                    widget_tree.get_object("toolbuttonPrevPage"),
                ],
                ActionMovePageIndex(self, -1),
            ),
            'next_page' : (
                [
                    widget_tree.get_object("toolbuttonNextPage"),
                ],
                ActionMovePageIndex(self, 1),
            ),
            'set_current_page' : (
                [
                    widget_tree.get_object("entryPageNb"),
                ],
                ActionOpenPageNb(self),
            ),
            'zoom_levels' : (
                [
                    widget_tree.get_object("comboboxZoom"),
                ],
                ActionRebuildPage(self)
            ),
            'search' : (
                [
                    self.search_field,
                ],
                ActionUpdateSearchResults(self),
            ),
            'toggle_label' : (
                [
                    widget_tree.get_object("cellrenderertoggleLabel"),
                ],
                ActionToggleLabel(self),
            ),
            'show_all_boxes' : (
                [
                    self.show_all_boxes
                ],
                ActionRebuildPage(self)
            ),
            'redo_ocr_doc': (
                [
                    widget_tree.get_object("menuitemReOcr"),
                ],
                ActionRedoDocOCR(self),
            ),
            'redo_ocr_all' : (
                [
                    widget_tree.get_object("menuitemReOcrAll"),
                ],
                ActionRedoAllOCR(self),
            ),
            'reindex' : (
                [
                    widget_tree.get_object("menuitemReindexAll"),
                ],
                ActionStartSimpleWorker(self.workers['reindex'])
            ),
            'about' : (
                [
                    widget_tree.get_object("menuitemAbout"),
                ],
                ActionAbout(self),
            ),
        }

        for action in self.actions:
            self.actions[action][1].connect(self.actions[action][0])

        for (buttons, action) in self.actions.values():
            for button in buttons:
                if isinstance(button, gtk.ToolButton):
                    button.set_tooltip_text(button.get_label())

        for button in self.actions['single_scan'][0]:
            # let's be more specific on the tool tips of these buttons
            if isinstance(button, gtk.ToolButton):
                button.set_tooltip_text(_("Scan single page"))

        self.need_doc_widgets = (
            self.actions['print'][0]
            + self.actions['create_label'][0]
            + self.actions['open_doc_dir'][0]
            + self.actions['del_doc'][0]
            + self.actions['set_current_page'][0]
            + self.actions['toggle_label'][0]
            + self.actions['redo_ocr_doc'][0]
        )

        self.need_page_widgets = (
            self.actions['del_page'][0]
            + self.actions['prev_page'][0]
            + self.actions['next_page'][0]
        )

        self.need_label_widgets = (
            self.actions['del_label'][0]
            + self.actions['edit_label'][0]
        )

        self.doc_edit_widgets = (
            self.actions['single_scan'][0]
            + self.actions['del_page'][0]
        )

        for popup_menu in self.popupMenus.values():
            # TODO(Jflesch): Find the correct signal
            # This one doesn't take into account the key to access these menus
            popup_menu[0].connect("button_press_event", self.__popup_menu_cb,
                                  popup_menu[0], popup_menu[1])

        self.img['eventbox'].add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.img['eventbox'].connect("motion-notify-event",
                                     self.__on_img_mouse_motion)

        self.window.connect("destroy",
                            ActionRealQuit(self, config).on_window_close_cb)

        self.workers['reindex'].connect('indexation-start', lambda indexer: \
            gobject.idle_add(self.__on_indexation_start_cb, indexer))
        self.workers['reindex'].connect('indexation-progression',
            lambda indexer, progression, txt: \
                gobject.idle_add(self.set_progression, indexer,
                                 progression, txt))
        self.workers['reindex'].connect('indexation-end', lambda indexer: \
            gobject.idle_add(self.__on_indexation_end_cb, indexer))

        self.workers['thumbnailer'].connect('thumbnailing-start',
                lambda thumbnailer: \
                    gobject.idle_add(self.__on_thumbnailing_start_cb,
                                     thumbnailer))
        self.workers['thumbnailer'].connect('thumbnailing-page-done',
                lambda thumbnailer, page_idx, thumbnail: \
                    gobject.idle_add(self.__on_thumbnailing_page_done_cb,
                                     thumbnailer, page_idx, thumbnail))
        self.workers['thumbnailer'].connect('thumbnailing-end',
                lambda thumbnailer: \
                    gobject.idle_add(self.__on_thumbnailing_end_cb,
                                     thumbnailer))

        self.workers['img_builder'].connect('img-building-start',
                lambda builder: \
                    gobject.idle_add(self.img['image'].set_from_stock,
                        gtk.STOCK_EXECUTE, gtk.ICON_SIZE_DIALOG))
        self.workers['img_builder'].connect('img-building-result-pixbuf',
                lambda builder, factor, img: \
                    gobject.idle_add(self.__on_img_building_result_pixbuf,
                                     builder, factor, img))
        self.workers['img_builder'].connect('img-building-result-stock',
                lambda builder, img: \
                    gobject.idle_add(self.img['image'].set_from_stock, img,
                                     gtk.ICON_SIZE_DIALOG))

        self.workers['label_updater'].connect('label-updating-start',
                lambda updater: \
                    gobject.idle_add(self.__on_label_updating_start_cb,
                                     updater))
        self.workers['label_updater'].connect('label-updating-doc-updated',
                lambda updater, progression, doc_name: \
                    gobject.idle_add(self.__on_label_updating_doc_updated_cb,
                                     updater, progression, doc_name))
        self.workers['label_updater'].connect('label-updating-end',
                lambda updater: \
                    gobject.idle_add(self.__on_label_updating_end_cb,
                                     updater))

        self.workers['label_deleter'].connect('label-deletion-start',
                lambda deleter: \
                    gobject.idle_add(self.__on_label_updating_start_cb,
                                     deleter))
        self.workers['label_deleter'].connect('label-deletion-doc-updated',
                lambda deleter, progression, doc_name: \
                    gobject.idle_add(self.__on_label_deletion_doc_updated_cb,
                                     deleter, progression, doc_name))
        self.workers['label_deleter'].connect('label-deletion-end',
                lambda deleter: \
                    gobject.idle_add(self.__on_label_updating_end_cb,
                                     deleter))

        self.workers['ocr_redoer'].connect('redo-ocr-start',
                lambda ocr_redoer: \
                    gobject.idle_add(self.__on_redo_ocr_start_cb,
                                     ocr_redoer))
        self.workers['ocr_redoer'].connect('redo-ocr-doc-updated',
                lambda ocr_redoer, progression, doc_name: \
                    gobject.idle_add(self.__on_redo_ocr_doc_updated_cb,
                                     ocr_redoer, progression, doc_name))
        self.workers['ocr_redoer'].connect('redo-ocr-end',
                lambda ocr_redoer: \
                    gobject.idle_add(self.__on_redo_ocr_end_cb,
                                     ocr_redoer))

        self.workers['single_scan'].connect('single-scan-start',
                lambda worker: \
                    gobject.idle_add(self.__on_single_scan_start, worker))
        self.workers['single_scan'].connect('single-scan-ocr',
                lambda worker: \
                    gobject.idle_add(self.__on_single_scan_ocr, worker))
        self.workers['single_scan'].connect('single-scan-done',
                lambda worker, page: \
                    gobject.idle_add(self.__on_single_scan_done, worker, page))

        self.window.connect("size-allocate", self.__on_window_resize_cb)

        self.window.set_visible(True)

    def set_search_availability(self, enabled):
        for list_view in self.doc_browsing.values():
            list_view.set_sensitive(enabled)

    def set_mouse_cursor(self, cursor):
        self.window.window.set_cursor({
            "Normal" : None,
            "Busy" : gtk.gdk.Cursor(gtk.gdk.WATCH),
        }[cursor])

    def set_progression(self, src, progression, text):
        context_id = self.status['text'].get_context_id(str(src))
        self.status['text'].pop(context_id)
        if (text != None and text != ""):
            self.status['text'].push(context_id, text)
        self.status['progress'].set_fraction(progression)

    def __on_indexation_start_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(False)
        self.set_mouse_cursor("Busy")

    def __on_indexation_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")
        self.refresh_doc_list()
        self.refresh_label_list()

    def __on_thumbnailing_start_cb(self, src):
        self.set_progression(src, 0.0, _("Thumbnailing ..."))
        self.set_mouse_cursor("Busy")

    def __on_thumbnailing_page_done_cb(self, src, page_idx, thumbnail):
        print "Updating thumbnail %d" % (page_idx)
        line_iter = self.lists['pages'][1].get_iter(page_idx)
        self.lists['pages'][1].set_value(line_iter, 0, thumbnail)
        self.lists['pages'][1].set_value(line_iter, 1, None)
        self.set_progression(src, ((float)(page_idx+1) / self.doc.nb_pages),
                             _("Thumbnailing ..."))

    def __on_thumbnailing_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")

    def __on_window_resize_cb(self, window, allocation):
        if (self.__win_size_cache == allocation):
            return
        self.__win_size_cache = allocation
        self.vpanels['txt_img_split'].set_position(0)

    def __on_label_updating_start_cb(self, src):
        self.set_search_availability(False)
        self.set_mouse_cursor("Busy")

    def __on_label_updating_doc_updated_cb(self, src, progression, doc_name):
        self.set_progression(src, progression,
                             _("Updating label (%s) ...") % (doc_name))

    def __on_label_deletion_doc_updated_cb(self, src, progression, doc_name):
        self.set_progression(src, progression,
                             _("Deleting label (%s) ...") % (doc_name))

    def __on_label_updating_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")
        self.refresh_label_list()
        self.refresh_doc_list()
        self.workers['reindex'].stop()
        self.workers['reindex'].start()

    def __on_redo_ocr_start_cb(self, src):
        self.set_search_availability(False)
        self.set_mouse_cursor("Busy")
        self.set_progression(src, progression,
                             _("Redoing OCR ..."))

    def __on_redo_ocr_doc_updated_cb(self, src, progression, doc_name):
        self.set_progression(src, progression,
                             _("Redoing OCR (%s) ...") % (doc_name))

    def __on_redo_ocr_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")
        self.refresh_label_list()
        self.refresh_doc_list()
        if self.page != None:
            # in case the keywords were highlighted
            self.show_page(self.page)
        self.workers['reindex'].stop()
        self.workers['reindex'].start()

    def __on_single_scan_start(self, src):
        self.set_progression(src, 0.0, _("Scanning ..."))
        self.set_mouse_cursor("Busy")
        self.img['image'].set_from_stock(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_DIALOG)

        self.__scan_start = time.time()
        self.workers['progress_updater'].start(
            value_min=0.0, value_max=0.5,
            total_time=self.__config.scan_time['normal'])

    def __on_single_scan_ocr(self, src):
        scan_stop = time.time()
        self.workers['progress_updater'].stop()
        self.__config.scan_time['normal'] = scan_stop - self.__scan_start

        self.set_progression(src, 0.5, _("Reading ..."))

        self.__scan_start = time.time()
        self.workers['progress_updater'].start(
            value_min=0.5, value_max=1.0,
            total_time=self.__config.scan_time['ocr'])

    def __on_single_scan_done(self, src, page):
        scan_stop = time.time()
        self.workers['progress_updater'].stop()
        self.__config.scan_time['ocr'] = scan_stop - self.__scan_start

        for widget in self.need_doc_widgets:
            widget.set_sensitive(True)

        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")
        self.workers['thumbnailer'].stop()
        self.refresh_page_list()
        self.workers['thumbnailer'].start()

        if page != None:
            self.show_page(page)

        self.workers['reindex'].stop()
        self.workers['reindex'].start()

    def __popup_menu_cb(self, ev_component, event, ui_component, popup_menu):
        # we are only interested in right clicks
        if event.button != 3 or event.type != gtk.gdk.BUTTON_PRESS:
            return
        popup_menu.popup(None, None, None, event.button, event.time)

    def __on_img_building_result_pixbuf(self, builder, factor, img):
        self.img['factor'] = factor
        self.img['pixbuf'] = img

        (pixmap, mask) = img.render_pixmap_and_mask()

        show_all = self.show_all_boxes.get_active()
        if show_all:
            box_list = self.img['boxes']['all']
        else:
            box_list = self.img['boxes']['highlighted']
        for box in box_list:
            self.__draw_box(pixmap, box)

        self.img['image'].set_from_pixmap(pixmap, mask)

    def __get_box_position(self, box, window=None, width=1):
        ((a, b), (c, d)) = box.position
        a *= self.img['factor']
        b *= self.img['factor']
        c *= self.img['factor']
        d *= self.img['factor']
        if window:
            (win_w, win_h) = window.get_size()
            (pic_w, pic_h) = (self.img['pixbuf'].get_width(),
                              self.img['pixbuf'].get_height())
            (margin_x, margin_y) = ((win_w-pic_w)/2, (win_h-pic_h)/2)
            a += margin_x
            b += margin_y
            c += margin_x
            d += margin_y
        a -= width
        b -= width
        c += width
        d += width
        return ((int(a), int(b)), (int(c), int(d)))

    def __draw_box(self, drawable, box):
        highlighted = (box in self.img['boxes']['highlighted'])
        width=1
        color='#6c5dd1'
        if highlighted:
            width=3
            color='#009f00'
        ((img_a, img_b), (img_c, img_d)) = \
                self.__get_box_position(box, window=drawable, width=0)
        cm = drawable.get_colormap()
        gc = drawable.new_gc(foreground=cm.alloc_color(color))
        for i in range(0, width):
            drawable.draw_rectangle(gc, False,
                                    x=img_a-i, y=img_b-i,
                                    width=(img_c-img_a+(2*i)),
                                    height=(img_d-img_b+(2*i)))
    
    def __undraw_box(self, drawable, box):
        ((img_a, img_b), (img_c, img_d)) = \
                self.__get_box_position(box, window=drawable, width=5)
        ((pic_a, pic_b), (pic_c, pic_d)) = \
                self.__get_box_position(box, window=None, width=5)
        gc = drawable.new_gc()
        drawable.draw_pixbuf(gc, self.img['pixbuf'],
                             src_x=pic_a, src_y=pic_b,
                             dest_x=img_a, dest_y=img_b,
                             width=(img_c-img_a),
                             height=(img_d-img_b))

        show_all = self.show_all_boxes.get_active()
        highlighted = (box in self.img['boxes']['highlighted'])
        if show_all or highlighted:
            # force redrawing
            self.__draw_box(drawable, box)

    def __on_img_mouse_motion(self, event_box, event):
        try:
            # make sure we have an image currently displayed
            self.img['image'].get_pixmap()
        except ValueError:
            return

        (mouse_x, mouse_y) = event.get_coords()

        old_box = self.img['boxes']['current']
        new_box = None
        for box in self.img['boxes']['all']:
            ((a, b), (c, d)) = \
                    self.__get_box_position(box,
                                            window=self.img['image'].window,
                                            width=0)
            if (mouse_x < a or mouse_y < b
                or mouse_x > c or mouse_y > d):
                continue
            new_box = box

        if old_box == new_box:
            return

        self.img['boxes']['current'] = new_box

        if old_box:
            self.img['image'].set_tooltip_text(None)
            self.__undraw_box(self.img['image'].window, old_box)
        if new_box:
            self.img['image'].set_tooltip_text(new_box.content)
            self.__draw_box(self.img['image'].window, new_box)

    def refresh_doc_list(self):
        """
        Update the suggestions list and the matching documents list based on
        the keywords typed by the user in the search field.
        """
        sentence = unicode(self.search_field.get_text())
        print "Search: %s" % (sentence.encode('ascii', 'replace'))

        suggestions = self.docsearch.find_suggestions(sentence)
        print "Got %d suggestions" % len(suggestions)
        self.lists['suggestions'][1].clear()
        for suggestion in suggestions:
            self.lists['suggestions'][1].append([suggestion])

        documents = self.docsearch.find_documents(sentence)
        print "Got %d documents" % len(documents)
        documents = reversed(documents)

        self.lists['matches'][1].clear()
        for doc in documents:
            labels = doc.labels
            final_str = "%s" % (doc.name)
            nb_pages = doc.nb_pages
            if nb_pages > 1:
                final_str += (_("\n  %d pages") % (doc.nb_pages))
            if len(labels) > 0:
                final_str += ("\n  "
                        + "\n  ".join([x.get_html() for x in labels]))
            self.lists['matches'][1].append([final_str, doc])

    def refresh_page_list(self):
        """
        Reload and refresh the page list.
        Warning: Will remove the thumbnails on all the pages
        """
        self.lists['pages'][1].clear()
        for page in self.doc.pages:
            self.lists['pages'][1].append([
                None,  # no thumbnail
                gtk.STOCK_EXECUTE,
                gtk.ICON_SIZE_DIALOG,
                _('Page %d') % (page.page_nb + 1),
                page.page_nb
            ])
        self.indicators['total_pages'].set_text(
                _("/ %d") % (self.doc.nb_pages))
        for widget in self.need_page_widgets:
            widget.set_sensitive(False)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(self.doc.can_edit)

    def refresh_label_list(self):
        """
        Reload and refresh the label list
        """
        self.lists['labels'][1].clear()
        labels = self.doc.labels
        for label in self.docsearch.label_list:
            self.lists['labels'][1].append([
                label.get_html(),
                (label in labels),
                label
            ])
        for widget in self.need_label_widgets:
            widget.set_sensitive(False)

    def refresh_highlighted_words(self):
        old_highlights = self.img['boxes']['highlighted']

        search = unicode(self.search_field.get_text())
        self.img['boxes']['highlighted'] = self.page.get_boxes(search)

        for box in old_highlights:
            self.__undraw_box(self.img['image'].window, box)
        for box in self.img['boxes']['highlighted']:
            self.__draw_box(self.img['image'].window, box)

    def show_page(self, page):
        print "Showing page %s" % (str(page))

        for widget in self.need_page_widgets:
            widget.set_sensitive(True)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(self.doc.can_edit)

        # TODO(Jflesch): We should not make assumption regarding
        # the page position in the list
        self.lists['pages'][0].select_path(page.page_nb)
        self.indicators['current_page'].set_text(
                "%d" % (page.page_nb + 1))

        self.workers['img_builder'].stop()

        self.page = page
        self.img['boxes']['all'] = self.page.boxes
        search = unicode(self.search_field.get_text())
        self.img['boxes']['highlighted'] = self.page.get_boxes(search)

        self.workers['img_builder'].start()

        txt = "\n".join(page.text)
        self.text_area.get_buffer().set_text(txt)

    def show_doc(self, doc):
        self.workers['thumbnailer'].stop()
        self.doc = doc
        for widget in self.need_doc_widgets:
            widget.set_sensitive(True)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(self.doc.can_edit)
        self.refresh_page_list()
        self.refresh_label_list()
        self.workers['thumbnailer'].start()
        self.show_page(self.doc.pages[0])

