#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
#    Copyright (C) 2012  Sebastien Maccagnoni-Munch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

from copy import copy
import os
import sys
import threading
import time

import Image
import ImageColor
import gettext
import cairo
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GdkPixbuf

import pyinsane.rawapi

from paperwork.frontend.aboutdialog import AboutDialog
from paperwork.frontend.actions import SimpleAction
from paperwork.frontend.multiscan import MultiscanDialog
from paperwork.frontend.settingswindow import SettingsWindow
from paperwork.frontend.workers import Worker
from paperwork.frontend.workers import WorkerProgressUpdater
from paperwork.backend import docimport
from paperwork.backend.common.page import DummyPage
from paperwork.backend.docsearch import DocSearch
from paperwork.backend.docsearch import DummyDocSearch
from paperwork.backend.img.doc import ImgDoc
from paperwork.backend.img.page import ImgPage
from paperwork.backend.labels import LabelEditor
from paperwork.util import add_img_border
from paperwork.util import ask_confirmation
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile
from paperwork.util import popup_no_scanner_found
from paperwork.util import sizeof_fmt

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


def check_scanner(main_win, config):
    if config.scanner_devid != None:
        return True
    main_win.actions['open_settings'][1].do()
    return False


class WorkerDocIndexer(Worker):
    """
    Reindex all the documents
    """

    __gsignals__ = {
        'indexation-start' : (GObject.SignalFlags.RUN_LAST, None, ()),
        'indexation-progression' : (GObject.SignalFlags.RUN_LAST, None,
                                    (GObject.TYPE_FLOAT, GObject.TYPE_STRING)),
        'indexation-end' : (GObject.SignalFlags.RUN_LAST, None, ()),
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
        elif step == DocSearch.INDEX_STEP_COMMIT:
            txt = _('Updating index ...')
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

GObject.type_register(WorkerDocIndexer)


class WorkerDocSearcher(Worker):
    """
    Search the documents
    """

    __gsignals__ = {
        'search-start' : (GObject.SignalFlags.RUN_LAST, None, ()),
        # first obj: array of documents
        # second obj: array of suggestions
        'search-result' : (GObject.SignalFlags.RUN_LAST, None,
                        (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT)),
    }

    can_interrupt = True

    def __init__(self, main_window, config):
        Worker.__init__(self, "Search")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        sentence = unicode(self.__main_win.search_field.get_text(), encoding='utf-8')

        self.emit('search-start')

        if not self.can_run:
            return

        documents = self.__main_win.docsearch.find_documents(sentence)
        if sentence == u"":
            # append a new document to the list
            documents.insert(0, ImgDoc(self.__config.workdir))

        suggestions = self.__main_win.docsearch.find_suggestions(sentence)

        self.emit('search-result', documents, suggestions)


GObject.type_register(WorkerDocSearcher)


class WorkerPageThumbnailer(Worker):
    """
    Generate page thumbnails
    """

    __gsignals__ = {
        'page-thumbnailing-start' :
            (GObject.SignalFlags.RUN_LAST, None, ()),
        'page-thumbnailing-page-done':
            (GObject.SignalFlags.RUN_LAST, None,
             (GObject.TYPE_INT, GObject.TYPE_PYOBJECT)),
        'page-thumbnailing-end' :
            (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_interrupt = True

    def __init__(self, main_window):
        Worker.__init__(self, "Page thumbnailing")
        self.__main_win = main_window

    def do(self):
        self.emit('page-thumbnailing-start')
        for page_idx in range(0, self.__main_win.doc.nb_pages):
            page = self.__main_win.doc.pages[page_idx]
            img = page.get_thumbnail(150)
            img = add_img_border(img)
            pixbuf = image2pixbuf(img)
            if not self.can_run:
                self.emit('page-thumbnailing-end')
                return
            self.emit('page-thumbnailing-page-done', page_idx, pixbuf)
        self.emit('page-thumbnailing-end')


GObject.type_register(WorkerPageThumbnailer)


class WorkerDocThumbnailer(Worker):
    """
    Generate doc list thumbnails
    """

    __gsignals__ = {
        'doc-thumbnailing-start' :
            (GObject.SignalFlags.RUN_LAST, None, ()),
        'doc-thumbnailing-doc-done':
            (GObject.SignalFlags.RUN_LAST, None,
             (GObject.TYPE_INT, GObject.TYPE_PYOBJECT)),
        'doc-thumbnailing-end' :
            (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_interrupt = True

    def __init__(self, main_window):
        Worker.__init__(self, "Doc thumbnailing")
        self.__main_win = main_window

    def do(self, doc_indexes=None):
        self.emit('doc-thumbnailing-start')

        doclist = self.__main_win.lists['matches']['doclist']
        if doc_indexes is None:
            doc_indexes = range(0, len(doclist))

        for doc_idx in doc_indexes:
            doc = doclist[doc_idx]
            if doc.nb_pages <= 0:
                continue
            img = doc.pages[0].get_thumbnail(150)
            img = add_img_border(img)
            pixbuf = image2pixbuf(img)
            if not self.can_run:
                self.emit('doc-thumbnailing-end')
                return
            self.emit('doc-thumbnailing-doc-done', doc_idx, pixbuf)
        self.emit('doc-thumbnailing-end')


GObject.type_register(WorkerDocThumbnailer)


class WorkerImgBuilder(Worker):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'img-building-start' :
            (GObject.SignalFlags.RUN_LAST, None, ()),
        'img-building-result-pixbuf' :
            (GObject.SignalFlags.RUN_LAST, None,
             (GObject.TYPE_FLOAT, GObject.TYPE_INT,
              GObject.TYPE_PYOBJECT,  # pixbuf
              GObject.TYPE_PYOBJECT,  # array of boxes
             )),
        'img-building-result-stock' :
            (GObject.SignalFlags.RUN_LAST, None,
             (GObject.TYPE_STRING, )),
    }

    # even if it's not true, this process is not really long, so it doesn't
    # really matter
    can_interrupt = True

    def __init__(self, main_window):
        Worker.__init__(self, "Building page image")
        self.__main_win = main_window

    def do(self):
        self.emit('img-building-start')

        if self.__main_win.page.img == None:
            self.emit('img-building-result-stock', Gtk.STOCK_MISSING_IMAGE)
            return

        # to keep the GUI smooth
        for t in range(0, 25):
            if not self.can_run:
                break
            time.sleep(0.01)
        if not self.can_run:
            self.emit('img-building-result-stock', Gtk.STOCK_DIALOG_ERROR)
            return

        try:
            img = self.__main_win.page.img

            pixbuf = image2pixbuf(img)
            original_width = pixbuf.get_width()

            factor = self.__main_win.get_zoom_factor(original_width)
            print "Zoom: %f" % (factor)

            wanted_width = int(factor * pixbuf.get_width())
            wanted_height = int(factor * pixbuf.get_height())
            pixbuf = pixbuf.scale_simple(wanted_width, wanted_height,
                                         GdkPixbuf.InterpType.BILINEAR)

            self.emit('img-building-result-pixbuf', factor, original_width,
                      pixbuf, self.__main_win.page.boxes)
        except Exception, exc:
            self.emit('img-building-result-stock', Gtk.STOCK_DIALOG_ERROR)
            raise exc


GObject.type_register(WorkerImgBuilder)


class WorkerLabelUpdater(Worker):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'label-updating-start' :
            (GObject.SignalFlags.RUN_LAST, None, ()),
        'label-updating-doc-updated' :
            (GObject.SignalFlags.RUN_LAST, None,
             (GObject.TYPE_FLOAT, GObject.TYPE_STRING)),
        'label-updating-end' : (GObject.SignalFlags.RUN_LAST, None, ()),
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


GObject.type_register(WorkerLabelUpdater)


class WorkerLabelDeleter(Worker):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'label-deletion-start' :
            (GObject.SignalFlags.RUN_LAST, None, ()),
        'label-deletion-doc-updated' :
            (GObject.SignalFlags.RUN_LAST, None,
             (GObject.TYPE_FLOAT, GObject.TYPE_STRING)),
        'label-deletion-end' : (GObject.SignalFlags.RUN_LAST, None, ()),
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


GObject.type_register(WorkerLabelDeleter)


class WorkerOCRRedoer(Worker):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'redo-ocr-start' :
            (GObject.SignalFlags.RUN_LAST, None, ()),
        'redo-ocr-doc-updated' :
            (GObject.SignalFlags.RUN_LAST, None,
             (GObject.TYPE_FLOAT, GObject.TYPE_STRING)),
        'redo-ocr-end' : (GObject.SignalFlags.RUN_LAST, None, ()),
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


GObject.type_register(WorkerOCRRedoer)


class WorkerSingleScan(Worker):
    __gsignals__ = {
        'single-scan-start' : (GObject.SignalFlags.RUN_LAST, None, ()),
        'single-scan-ocr' : (GObject.SignalFlags.RUN_LAST, None, ()),
        'single-scan-done' : (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_PYOBJECT,) # ImgPage
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
            try:
                scanner.options['source'].value = "Auto"
            except pyinsane.rawapi.SaneException, exc:
                print ("Warning: Unable to set scanner source to 'Auto': %s" %
                       (str(exc)))
            scan_src = scanner.scan(multiple=False)
        except pyinsane.rawapi.SaneException, exc:
            print "No scanner found !"
            GObject.idle_add(popup_no_scanner_found, self.__main_win.window)
            self.emit('single-scan-done', None)
            raise
        doc.scan_single_page(scan_src, scanner.options['resolution'].value,
                             self.__config.scanner_calibration,
                             self.__config.ocrlang,
                             self.__scan_progress_cb)
        page = doc.pages[doc.nb_pages - 1]
        self.__main_win.docsearch.index_page(page)

        self.emit('single-scan-done', page)


GObject.type_register(WorkerSingleScan)


class WorkerImporter(Worker):
    __gsignals__ = {
        'import-start' : (GObject.SignalFlags.RUN_LAST, None, ()),
        'import-done' : (GObject.SignalFlags.RUN_LAST, None,
                         (GObject.TYPE_PYOBJECT,  # Doc
                          GObject.TYPE_PYOBJECT),  # Page
                        ),
    }

    can_interrupt = True

    def __init__(self, main_window, config):
        Worker.__init__(self, "Importing file")
        self.__main_win = main_window
        self.__config = config

    def do(self, importer, file_uri):
        self.emit('import-start')
        (doc, page) = importer.import_doc(file_uri, self.__config,
                                  self.__main_win.docsearch,
                                  self.__main_win.doc)
        self.emit('import-done', doc, page)


GObject.type_register(WorkerImporter)


class WorkerExportPreviewer(Worker):
    __gsignals__ = {
        'export-preview-start' : (GObject.SignalFlags.RUN_LAST, None,
                                 ()),
        'export-preview-done' : (GObject.SignalFlags.RUN_LAST, None,
                                 (GObject.TYPE_INT, GObject.TYPE_PYOBJECT,)),
    }

    can_interrupt = True

    def __init__(self, main_window):
        Worker.__init__(self, "Export previewer")
        self.__main_win = main_window

    def do(self):
        for i in range(0, 7):
            time.sleep(0.1)
            if not self.can_run:
                return
        self.emit('export-preview-start')
        size = self.__main_win.export['exporter'].estimate_size()
        img = self.__main_win.export['exporter'].get_img()
        pixbuf = image2pixbuf(img)
        self.emit('export-preview-done', size, pixbuf)


GObject.type_register(WorkerExportPreviewer)


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

        must_insert_new = False

        doclist = self.__main_win.lists['matches']['doclist']
        if (len(doclist) <= 0):
            must_insert_new = True
        else:
            must_insert_new = not doclist[0].is_new

        if must_insert_new:
            doc = ImgDoc(self.__config.workdir)
            doclist.insert(0, doc)
            self.__main_win.lists['matches']['model'].insert(
                0,
                [
                    doc.name,
                    doc,
                    None,
                    None,
                    Gtk.IconSize.DIALOG,
                ])

        path = Gtk.TreePath(0)
        self.__main_win.lists['matches']['gui'].select_path(path)
        self.__main_win.lists['matches']['gui'].scroll_to_path(
            path, False, 0.0, 0.0)


class ActionOpenSelectedDocument(SimpleAction):
    """
    Starts a new document.
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open selected document")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        selection_path = \
                self.__main_win.lists['matches']['gui'].get_selected_items()
        if len(selection_path) <= 0:
            print "No document selected. Can't open"
            return
        doc_idx = selection_path[0].get_indices()[0]
        doc = self.__main_win.lists['matches']['model'][doc_idx][1]

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


class ActionStartSearch(SimpleAction):
    """
    Let the user type keywords to do a document search
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Focus on search field")
        self.__main_win = main_window

    def do(self):
        self.__main_win.search_field.grab_focus()


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
        self.__main_win.refresh_page()

    def on_icon_press_cb(self, entry, iconpos=Gtk.EntryIconPosition.SECONDARY, event=None):
        if iconpos == Gtk.EntryIconPosition.PRIMARY:
            entry.grab_focus()
        else:
            entry.set_text("")


class ActionOpenPageSelected(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self,
                "Show a page (selected from the page thumbnail list)")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        selection_path = self.__main_win.lists['pages']['gui'].get_selected_items()
        if len(selection_path) <= 0:
            self.__main_win.show_page(DummyPage(self.__main_win.doc))
            return
        # TODO(Jflesch): We should get the page number from the list content,
        # not from the position of the element in the list
        page_idx = selection_path[0].get_indices()[0]
        page = self.__main_win.doc.pages[page_idx]
        self.__main_win.show_page(page)


class ActionMovePageIndex(SimpleAction):
    def __init__(self, main_window, relative=True, value=0):
        if relative:
            txt = "previous"
            if value > 0:
                txt = "next"
        else:
            if value < 0:
                txt = "last"
            else:
                txt = "page %d" % (value)
        SimpleAction.__init__(self, ("Show the %s page" % (txt)))
        self.relative = relative
        self.value = value
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        page_idx = self.__main_win.page.page_nb
        if self.relative:
            page_idx += self.value
        elif self.value < 0:
            page_idx = self.__main_win.doc.nb_pages - 1
        else:
            page_idx = self.value
        if page_idx < 0 or page_idx >= self.__main_win.doc.nb_pages:
            return
        page = self.__main_win.doc.pages[page_idx]
        self.__main_win.show_page(page)


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
        SimpleAction.__init__(self, "Reload current page")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.workers['img_builder'].stop()
        self.__main_win.workers['img_builder'].start()


class ActionRefreshPage(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Refresh current page")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_page()


class ActionLabelSelected(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Label selected")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        for widget in self.__main_win.need_label_widgets:
            widget.set_sensitive(True)
        return True


class ActionToggleLabel(object):
    def __init__(self, main_window):
        self.__main_win = main_window

    def toggle_cb(self, renderer, objpath):
        label = self.__main_win.lists['labels']['model'][objpath][2]
        if not label in self.__main_win.doc.labels:
            print ("Action: Adding label '%s' on document '%s'"
                   % (str(label), str(self.__main_win.doc)))
            self.__main_win.docsearch.add_label(self.__main_win.doc, label)
        else:
            print ("Action: Removing label '%s' on document '%s'"
                   % (str(label), str(self.__main_win.doc)))
            self.__main_win.docsearch.remove_label(self.__main_win.doc, label)
        self.__main_win.refresh_label_list()
        self.__main_win.refresh_docs([self.__main_win.doc])

    def connect(self, cellrenderers):
        for cellrenderer in cellrenderers:
            cellrenderer.connect('toggled', self.toggle_cb)


class ActionCreateLabel(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Creating label")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        labeleditor = LabelEditor()
        if labeleditor.edit(self.__main_win.window):
            print "Adding label %s to doc %s" % (str(labeleditor.label),
                                                 str(self.__main_win.doc))
            self.__main_win.docsearch.add_label(self.__main_win.doc,
                                                labeleditor.label)
        self.__main_win.refresh_label_list()
        self.__main_win.refresh_docs([self.__main_win.doc])


class ActionEditLabel(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Editing label")
        self.__main_win = main_window

    def do(self):
        if self.__main_win.workers['label_updater'].is_running:
            return

        SimpleAction.do(self)

        selection_path = self.__main_win.lists['labels']['gui'] \
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

        SimpleAction.do(self)

        if not ask_confirmation(self.__main_win.window):
            return

        selection_path = self.__main_win.lists['labels']['gui'] \
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
        SimpleAction.do(self)
        os.system('xdg-open "%s"' % (self.__main_win.doc.path))


class ActionPrintDoc(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open print dialog")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        print_settings = Gtk.PrintSettings()
        # By default, print context are using 72 dpi, but print_draw_page
        # will change it to 300 dpi --> we have to tell PrintOperation to scale
        print_settings.set_scale(100.0 * (72.0 / ImgPage.PRINT_RESOLUTION))

        print_op = Gtk.PrintOperation()
        print_op.set_print_settings(print_settings)
        print_op.set_n_pages(self.__main_win.doc.nb_pages)
        print_op.set_current_page(self.__main_win.page.page_nb)
        print_op.set_use_full_page(True)
        print_op.set_job_name(str(self.__main_win.doc))
        print_op.set_export_filename(str(self.__main_win.doc) + ".pdf")
        print_op.set_allow_async(True)
        print_op.connect("draw-page", self.__main_win.doc.print_page_cb)
        print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG,
                     self.__main_win.window)


class ActionOpenSettings(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Open settings dialog")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
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
        SimpleAction.do(self)
        check_workdir(self.__config)
        if not check_scanner(self.__main_win, self.__config):
            return
        self.__main_win.workers['single_scan'].start(
                doc=self.__main_win.doc)


class ActionMultiScan(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Scan multiples pages")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        check_workdir(self.__config)
        if not check_scanner(self.__main_win, self.__config):
            return
        ms = MultiscanDialog(self.__main_win, self.__config)
        ms.connect("need-doclist-refresh", self.__doclist_refresh)

    def __doclist_refresh(self, multiscan_window):
        self.__main_win.refresh_doc_list()


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

        response = dialog.run()
        if response != 0:
            print "Import: Canceled by user"
            dialog.destroy()
            return None
        file_uri = dialog.get_uri()
        dialog.destroy()
        print "Import: %s" % file_uri
        return file_uri

    def __select_importer(self, importers):
        widget_tree = load_uifile("import_select.glade")
        combobox = widget_tree.get_object("comboboxImportAction")
        importer_list = widget_tree.get_object("liststoreImportAction")
        dialog = widget_tree.get_object("dialogImportSelect")

        importer_list.clear()
        for importer in importers:
            importer_list.append([str(importer), importer])

        response = dialog.run()
        if not response:
            raise Exception("Import cancelled by user")

        active_idx = combobox.get_active()
        return import_list[active_idx][1]

    def do(self):
        SimpleAction.do(self)

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
                Gtk.MessageDialog(parent=self.__main_win.window,
                                  flags=(Gtk.DialogFlags.MODAL
                                         |Gtk.DialogFlags.DESTROY_WITH_PARENT),
                                  type=Gtk.MessageType.ERROR,
                                  buttons=Gtk.ButtonsType.OK,
                                  message_format=msg)
            dialog.run()
            dialog.destroy()
            return

        if len(importers) > 1:
            importer = self.__select_importers(importers)
        else:
            importer = importers[0]

        Gtk.RecentManager().add_item(file_uri)

        self.__main_win.workers['importer'].start(
            importer=importer, file_uri = file_uri)


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
        SimpleAction.do(self)
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
        SimpleAction.do(self)
        print "Deleting ..."
        self.__main_win.page.destroy()
        print "Deleted"
        self.__main_win.page = None
        for widget in self.__main_win.need_page_widgets:
            widget.set_sensitive(False)
        self.__main_win.refresh_page_list()
        self.__main_win.refresh_label_list()


class ActionRedoDocOCR(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Redoing doc ocr")
        self.__main_win = main_window

    def do(self):
        if not ask_confirmation(self.__main_win.window):
            return
        SimpleAction.do(self)

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
        SimpleAction.do(self)

        if self.__main_win.workers['ocr_redoer'].is_running:
            return

        self.__main_win.workers['ocr_redoer'].start(doc_target=self.__main_win.docsearch)


class BasicActionOpenExportDialog(SimpleAction):
    def __init__(self, main_window, action_txt):
        SimpleAction.__init__(self, action_txt)
        self.main_win = main_window

    def open_dialog(self, to_export):
        SimpleAction.do(self)
        self.main_win.export['estimated_size'].set_text("")
        self.main_win.export['format']['store'].clear()
        nb_export_formats = 0
        for out_format in to_export.get_export_formats():
            self.main_win.export['format']['store'].append([out_format])
            nb_export_formats += 1
        self.main_win.export['buttons']['select_path'].set_sensitive(
            nb_export_formats >= 1)
        self.main_win.export['format']['widget'].set_active(0)
        self.main_win.export['dialog'].set_visible(True)
        self.main_win.export['buttons']['ok'].set_sensitive(False)
        self.main_win.export['export_path'].set_text("")


class ActionOpenExportPageDialog(BasicActionOpenExportDialog):
    def __init__(self, main_window):
        BasicActionOpenExportDialog.__init__(self, main_window,
                                             "Displaying page export dialog")

    def do(self):
        SimpleAction.do(self)
        self.main_win.export['to_export'] = self.main_win.page
        self.main_win.export['buttons']['ok'].set_label(_("Export page"))
        BasicActionOpenExportDialog.open_dialog(self, self.main_win.page)


class ActionOpenExportDocDialog(BasicActionOpenExportDialog):
    def __init__(self, main_window):
        BasicActionOpenExportDialog.__init__(self, main_window,
                                   "Displaying page export dialog")

    def do(self):
        SimpleAction.do(self)
        self.main_win.export['to_export'] = self.main_win.doc
        self.main_win.export['buttons']['ok'].set_label(_("Export document"))
        BasicActionOpenExportDialog.open_dialog(self, self.main_win.doc)


class ActionSelectExportFormat(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Select export format")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        format_idx = self.__main_win.export['format']['widget'].get_active()
        imgformat = self.__main_win.export['format']['store'][format_idx][0]

        exporter = self.__main_win.export['to_export'].build_exporter(imgformat)
        self.__main_win.export['exporter'] = exporter
        self.__main_win.export['quality']['widget'].set_sensitive(
                exporter.can_change_quality)
        self.__main_win.export['quality']['label'].set_sensitive(
                exporter.can_change_quality)

        if exporter.can_change_quality:
            quality = self.__main_win.export['quality']['model'].get_value()
            self.__main_win.export['exporter'].set_quality(quality)
            self.__main_win.refresh_export_preview()
        else:
            size_txt = sizeof_fmt(exporter.estimate_size())
            self.__main_win.export['estimated_size'].set_text(size_txt)


class ActionSelectExportQuality(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Select export quality")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        if self.__main_win.export['exporter'].can_change_quality:
            quality = self.__main_win.export['quality']['model'].get_value()
            self.__main_win.export['exporter'].set_quality(quality)
            self.__main_win.refresh_export_preview()


class ActionSelectExportPath(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Select export path")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        chooser = Gtk.FileChooserDialog(title=_("Save as"),
                                        parent=self.__main_win.window,
                                        action=Gtk.FileChooserAction.SAVE,
                                        buttons=(Gtk.STOCK_CANCEL,
                                                 Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_SAVE,
                                                 Gtk.ResponseType.OK))
        file_filter = Gtk.FileFilter()
        file_filter.set_name(str(self.__main_win.export['exporter']))
        file_filter.add_mime_type(
                self.__main_win.export['exporter'].get_mime_type())
        chooser.add_filter(file_filter)

        response = chooser.run()
        filepath = chooser.get_filename()
        chooser.destroy()
        if response != Gtk.ResponseType.OK:
            print "File path for export canceled"
            return

        valid_exts = self.__main_win.export['exporter'].get_file_extensions()
        has_valid_ext = False
        for valid_ext in valid_exts:
            if filepath.lower().endswith(valid_ext.lower()):
                has_valid_ext = True
                break
        if not has_valid_ext:
            filepath += ".%s" % valid_exts[0]

        self.__main_win.export['export_path'].set_text(filepath)
        self.__main_win.export['buttons']['ok'].set_sensitive(True)


class ActionExport(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Export")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        filepath = self.__main_win.export['export_path'].get_text()
        self.__main_win.export['exporter'].save(filepath)
        SimpleAction.do(self)
        self.__main_win.export['dialog'].set_visible(False)


class ActionCancelExport(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Cancel export")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.export['dialog'].set_visible(False)


class ActionSetToolbarVisibility(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Set toolbar visibility")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        visible = self.__main_win.show_toolbar.get_active()
        if self.__config.toolbar_visible != visible:
            self.__config.toolbar_visible = visible
        for toolbar in self.__main_win.toolbars:
            toolbar.set_visible(visible)

class ActionZoomChange(SimpleAction):
    def __init__(self, main_window, offset):
        SimpleAction.__init__(self, "Zoom += %d" % offset)
        self.__main_win = main_window
        self.__offset = offset

    def do(self):
        SimpleAction.do(self)

        zoom_liststore = self.__main_win.lists['zoom_levels']['model']

        zoom_list = [
            (zoom_liststore[zoom_idx][1], zoom_idx)
            for zoom_idx in range(0, len(zoom_liststore))
        ]
        zoom_list.append((99999.0, -1))
        zoom_list.sort()

        current_zoom = self.__main_win.get_zoom_factor()

        # figures out where the current zoom fits in the zoom list
        current_idx = -1

        for zoom_list_idx in range(0, len(zoom_list)):
            if (zoom_list[zoom_list_idx][0] == 0.0):
                continue
            print ("%f <= %f < %f ?" % (zoom_list[zoom_list_idx][0],
                                       current_zoom,
                                       zoom_list[zoom_list_idx+1][0]))
            if (zoom_list[zoom_list_idx][0] <= current_zoom
                and current_zoom < zoom_list[zoom_list_idx+1][0]):
                current_idx = zoom_list_idx
                break

        assert(current_idx >= 0)

        # apply the change
        current_idx += self.__offset

        if (current_idx < 0 or current_idx >= len(zoom_liststore)):
            return

        if zoom_list[current_idx][0] == 0.0:
            return

        self.__main_win.lists['zoom_levels']['gui'].set_active(
                zoom_list[current_idx][1])


class ActionZoomSet(SimpleAction):
    def __init__(self, main_window, value):
        SimpleAction.__init__(self, ("Zoom = %f" % value))
        self.__main_win = main_window
        self.__value = value

    def do(self):
        SimpleAction.do(self)

        zoom_liststore = self.__main_win.lists['zoom_levels']['model']

        new_idx = -1
        for zoom_idx in range(0, len(zoom_liststore)):
            if (zoom_liststore[zoom_idx][1] == self.__value):
                new_idx = zoom_idx
                break
        assert(new_idx >= 0)

        self.__main_win.lists['zoom_levels']['gui'].set_active(new_idx)


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
        Gtk.main_quit()

    def on_window_close_cb(self, window):
        self.do()


class ActionRebuildIndex(SimpleAction):
    def __init__(self, main_window, config, force=False):
        SimpleAction.__init__(self, "Rebuild index")
        self.__main_win = main_window
        self.__config = config
        self.__force = force

    def do(self):
        SimpleAction.do(self)
        self.__main_win.workers['reindex'].stop()
        docsearch = self.__main_win.docsearch
        self.__main_win.docsearch = DummyDocSearch()
        if self.__force:
            docsearch.destroy_index()
        self.__main_win.workers['reindex'].start()


class MainWindow(object):
    def __init__(self, config):
        # used by the set_mouse_cursor() function to keep track of how many
        # threads requested a busy mouse cursor
        self.__busy_mouse_counter = 0
        self.__last_highlight_update = time.time()

        widget_tree = load_uifile("mainwindow.glade")

        self.window = widget_tree.get_object("mainWindow")

        self.__config = config
        self.__scan_start = 0.0

        self.docsearch = DummyDocSearch()
        self.doc = ImgDoc(self.__config.workdir)
        self.page = DummyPage(self.doc)

        self.lists = {
            'suggestions' : {
                'gui' : widget_tree.get_object("entrySearch"),
                'model' : widget_tree.get_object("liststoreSuggestion")
            },
            'matches' : {
                'gui' : widget_tree.get_object("iconviewMatch"),
                'model' : widget_tree.get_object("liststoreMatch"),
                'doclist' : [],
                'active_idx' : -1,
            },
            'pages' : {
                'gui' : widget_tree.get_object("iconviewPage"),
                'model' : widget_tree.get_object("liststorePage"),
            },
            'labels' : {
                'gui' : widget_tree.get_object("treeviewLabel"),
                'model' : widget_tree.get_object("liststoreLabel"),
            },
            'zoom_levels' : {
                'gui' : widget_tree.get_object("comboboxZoom"),
                'model' : widget_tree.get_object("liststoreZoom"),
            },
        }

        search_completion = Gtk.EntryCompletion()
        search_completion.set_model(self.lists['suggestions']['model'])
        search_completion.set_text_column(0)
        search_completion.set_match_func(lambda a, b, c, d: True, None)
        self.lists['suggestions']['gui'].set_completion(search_completion)

        self.indicators = {
            'current_page' : widget_tree.get_object("entryPageNb"),
            'total_pages' : widget_tree.get_object("labelTotalPages"),
        }

        self.search_field = widget_tree.get_object("entrySearch")
        self.search_field.set_tooltip_text(
            _('Search documents')
            + _('\n* To search documents with a specific label: label:[label]')
            + _('\n* Only the documents with a specific keyword: "[keyword]"')
            + _('\n* Ignore documents containing a specific keyword: NOT [keyword]')
            + _('\n* Find documents with one word or another: [keyword] OR [keyword]')
            )

        self.doc_browsing = {
            'matches' : widget_tree.get_object("iconviewMatch"),
            'pages' : widget_tree.get_object("iconviewPage"),
            'labels' : widget_tree.get_object("treeviewLabel"),
            'search' : self.search_field,
        }

        self.img = {
            "image" : widget_tree.get_object("imagePageImg"),
            "scrollbar" : widget_tree.get_object("scrolledwindowPageImg"),
            "viewport" : {
                "widget" : widget_tree.get_object("viewportImg"),
                "size" : (0, 0),
            },
            "eventbox" : widget_tree.get_object("eventboxImg"),
            "pixbuf" : None,
            "factor" : 1.0,
            "original_width" : 1,
            "boxes" : {
                'all' : [],
                'visible' : [],
                'highlighted' : [],
                'selected' : [],
            }
        }

        self.status = {
            'progress' : widget_tree.get_object("progressbar"),
            'text' : widget_tree.get_object("statusbar"),
        }

        self.popup_menus = {
            'labels' : (
                widget_tree.get_object("treeviewLabel"),
                widget_tree.get_object("popupmenuLabels")
            ),
            'matches' : (
                widget_tree.get_object("iconviewMatch"),
                widget_tree.get_object("popupmenuMatchs")
            ),
            'pages' : (
                widget_tree.get_object("iconviewPage"),
                widget_tree.get_object("popupmenuPages")
            )
        }

        self.show_all_boxes = \
            widget_tree.get_object("checkmenuitemShowAllBoxes")
        self.show_toolbar = \
            widget_tree.get_object("menuitemToolbarVisible")
        self.show_toolbar.set_active(config.toolbar_visible)

        self.toolbars = [
            widget_tree.get_object("toolbarMainWin"),
            widget_tree.get_object("toolbarPage"),
        ]
        for toolbar in self.toolbars:
            toolbar.set_visible(config.toolbar_visible)

        self.export = {
            'dialog' : widget_tree.get_object("infobarExport"),
            'format' : {
                'widget' : widget_tree.get_object("comboboxExportFormat"),
                'store' : widget_tree.get_object("liststoreExportFormat"),
            },
            'quality' : {
                'label' : widget_tree.get_object("labelExportQuality"),
                'widget' : widget_tree.get_object("scaleQuality"),
                'model' : widget_tree.get_object("adjustmentQuality"),
            },
            'estimated_size' : \
                widget_tree.get_object("labelEstimatedExportSize"),
            'export_path' : widget_tree.get_object("entryExportPath"),
            'buttons' : {
                'select_path' : widget_tree.get_object("buttonSelectExportPath"),
                'ok' : widget_tree.get_object("buttonExport"),
                'cancel' : widget_tree.get_object("buttonCancelExport"),
            },
            'to_export' : None,  # usually self.page or self.doc
            'exporter' : None,
        }

        self.workers = {
            'reindex' : WorkerDocIndexer(self, config),
            'searcher' : WorkerDocSearcher(self, config),
            'page_thumbnailer' : WorkerPageThumbnailer(self),
            'doc_thumbnailer' : WorkerDocThumbnailer(self),
            'img_builder' : WorkerImgBuilder(self),
            'label_updater' : WorkerLabelUpdater(self),
            'label_deleter' : WorkerLabelDeleter(self),
            'single_scan' : WorkerSingleScan(self, config),
            'importer' : WorkerImporter(self, config),
            'progress_updater' : WorkerProgressUpdater(
                "main window progress bar", self.status['progress']),
            'ocr_redoer' : WorkerOCRRedoer(self, config),
            'export_previewer' : WorkerExportPreviewer(self),
        }

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
                    widget_tree.get_object("iconviewMatch"),
                ],
                ActionOpenSelectedDocument(self)
            ),
            'open_page' : (
                [
                    widget_tree.get_object("iconviewPage"),
                ],
                ActionOpenPageSelected(self)
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
                    widget_tree.get_object("menuitemPrint1"),
                    widget_tree.get_object("toolbuttonPrint"),
                ],
                ActionPrintDoc(self)
            ),
            'open_export_doc_dialog' : (
                [
                    widget_tree.get_object("menuitemExportDoc"),
                    widget_tree.get_object("menuitemExportDoc1"),
                ],
                ActionOpenExportDocDialog(self)
            ),
            'open_export_page_dialog' : (
                [
                    widget_tree.get_object("menuitemExportPage"),
                    widget_tree.get_object("menuitemExportPage1"),
                ],
                ActionOpenExportPageDialog(self)
            ),
            'cancel_export' : (
                [widget_tree.get_object("buttonCancelExport")],
                ActionCancelExport(self),
            ),
            'select_export_format' : (
                [widget_tree.get_object("comboboxExportFormat")],
                ActionSelectExportFormat(self),
            ),
            'select_export_quality' : (
                [widget_tree.get_object("scaleQuality")],
                ActionSelectExportQuality(self),
            ),
            'select_export_path' : (
                [widget_tree.get_object("buttonSelectExportPath")],
                ActionSelectExportPath(self),
            ),
            'export' : (
                [widget_tree.get_object("buttonExport")],
                ActionExport(self),
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
                    widget_tree.get_object("menuitemOpenParentDir"),
                    widget_tree.get_object("menuitemOpenDocDir"),
                    widget_tree.get_object("toolbuttonOpenDocDir"),
                ],
                ActionOpenDocDir(self),
            ),
            'del_doc' : (
                [
                    widget_tree.get_object("menuitemDestroyDoc"),
                    widget_tree.get_object("menuitemDestroyDoc2"),
                    widget_tree.get_object("toolbuttonDeleteDoc"),
                ],
                ActionDeleteDoc(self),
            ),
            'del_page' : (
                [
                    widget_tree.get_object("menuitemDestroyPage"),
                    widget_tree.get_object("menuitemDestroyPage2"),
                    widget_tree.get_object("buttonDeletePage"),
                ],
                ActionDeletePage(self),
            ),
            'first_page' : (
                [
                    widget_tree.get_object("menuitemFirstPage"),
                ],
                ActionMovePageIndex(self, False, 0),
            ),
            'prev_page' : (
                [
                    widget_tree.get_object("menuitemPrevPage"),
                    widget_tree.get_object("toolbuttonPrevPage"),
                ],
                ActionMovePageIndex(self, True, -1),
            ),
            'next_page' : (
                [
                    widget_tree.get_object("menuitemNextPage"),
                    widget_tree.get_object("toolbuttonNextPage"),
                ],
                ActionMovePageIndex(self, True, 1),
            ),
            'last_page' : (
                [
                    widget_tree.get_object("menuitemLastPage"),
                ],
                ActionMovePageIndex(self, False, -1),
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
            'zoom_in' : (
                [
                    widget_tree.get_object("menuitemZoomIn"),
                ],
                ActionZoomChange(self, 1)
            ),
            'zoom_out' : (
                [
                    widget_tree.get_object("menuitemZoomOut"),
                ],
                ActionZoomChange(self, -1)
            ),
            'zoom_best_fit' : (
                [
                    widget_tree.get_object("menuitemZoomBestFit"),
                ],
                ActionZoomSet(self, 0.0)
            ),
            'zoom_normal' : (
                [
                    widget_tree.get_object("menuitemZoomNormal"),
                ],
                ActionZoomSet(self, 1.0)
            ),
            'start_search' : (
                [
                    widget_tree.get_object("menuitemFindTxt"),
                ],
                ActionStartSearch(self)
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
                ActionRefreshPage(self)
            ),
            'show_toolbar' : (
                [
                    self.show_toolbar,
                ],
                ActionSetToolbarVisibility(self, config),
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
                ActionRebuildIndex(self, config, force=True),
            ),
            'about' : (
                [
                    widget_tree.get_object("menuitemAbout"),
                ],
                ActionAbout(self),
            ),
        }

        for action in self.actions:
            for button in self.actions[action][0]:
                if button is None:
                    print "MISSING BUTTON: %s" % (action)
            self.actions[action][1].connect(self.actions[action][0])

        for (buttons, action) in self.actions.values():
            for button in buttons:
                if isinstance(button, Gtk.ToolButton):
                    button.set_tooltip_text(button.get_label())

        for button in self.actions['single_scan'][0]:
            # let's be more specific on the tool tips of these buttons
            if isinstance(button, Gtk.ToolButton):
                button.set_tooltip_text(_("Scan single page"))

        self.need_doc_widgets = (
            self.actions['print'][0]
            + self.actions['create_label'][0]
            + self.actions['open_doc_dir'][0]
            + self.actions['del_doc'][0]
            + self.actions['set_current_page'][0]
            + self.actions['toggle_label'][0]
            + self.actions['redo_ocr_doc'][0]
            + self.actions['open_export_doc_dialog'][0]
        )

        self.need_page_widgets = (
            self.actions['del_page'][0]
            + self.actions['first_page'][0]
            + self.actions['prev_page'][0]
            + self.actions['next_page'][0]
            + self.actions['last_page'][0]
            + self.actions['open_export_page_dialog'][0]
        )

        self.need_label_widgets = (
            self.actions['del_label'][0]
            + self.actions['edit_label'][0]
        )

        self.doc_edit_widgets = (
            self.actions['single_scan'][0]
            + self.actions['del_page'][0]
        )

        for (popup_menu_name, popup_menu) in self.popup_menus.iteritems():
            # TODO(Jflesch): Find the correct signal
            # This one doesn't take into account the key to access these menus
            if popup_menu[0] is None:
                print "MISSING POPUP MENU: %s" % popup_menu_name
            popup_menu[0].connect("button_press_event", self.__popup_menu_cb,
                                  popup_menu[0], popup_menu[1])

        self.img['eventbox'].add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.img['eventbox'].connect("motion-notify-event",
                                     self.__on_img_mouse_motion)

        self.window.connect("destroy",
                            ActionRealQuit(self, config).on_window_close_cb)

        self.workers['reindex'].connect('indexation-start', lambda indexer: \
            GObject.idle_add(self.__on_indexation_start_cb, indexer))
        self.workers['reindex'].connect('indexation-progression',
            lambda indexer, progression, txt: \
                GObject.idle_add(self.set_progression, indexer,
                                 progression, txt))
        self.workers['reindex'].connect('indexation-end', lambda indexer: \
            GObject.idle_add(self.__on_indexation_end_cb, indexer))

        self.workers['searcher'].connect('search-result', \
            lambda searcher, documents, suggestions: \
                GObject.idle_add(self.__on_search_result_cb, documents,
                                 suggestions))

        self.workers['page_thumbnailer'].connect('page-thumbnailing-start',
                lambda thumbnailer: \
                    GObject.idle_add(self.__on_page_thumbnailing_start_cb,
                                     thumbnailer))
        self.workers['page_thumbnailer'].connect('page-thumbnailing-page-done',
                lambda thumbnailer, page_idx, thumbnail: \
                    GObject.idle_add(self.__on_page_thumbnailing_page_done_cb,
                                     thumbnailer, page_idx, thumbnail))
        self.workers['page_thumbnailer'].connect('page-thumbnailing-end',
                lambda thumbnailer: \
                    GObject.idle_add(self.__on_page_thumbnailing_end_cb,
                                     thumbnailer))

        self.workers['doc_thumbnailer'].connect('doc-thumbnailing-start',
                lambda thumbnailer: \
                    GObject.idle_add(self.__on_doc_thumbnailing_start_cb,
                                     thumbnailer))
        self.workers['doc_thumbnailer'].connect('doc-thumbnailing-doc-done',
                lambda thumbnailer, doc_idx, thumbnail: \
                    GObject.idle_add(self.__on_doc_thumbnailing_doc_done_cb,
                                     thumbnailer, doc_idx, thumbnail))
        self.workers['doc_thumbnailer'].connect('doc-thumbnailing-end',
                lambda thumbnailer: \
                    GObject.idle_add(self.__on_doc_thumbnailing_end_cb,
                                     thumbnailer))

        self.workers['img_builder'].connect('img-building-start',
                lambda builder: \
                    GObject.idle_add(self.__on_img_building_start))
        self.workers['img_builder'].connect('img-building-result-pixbuf',
                lambda builder, factor, original_width, img, boxes: \
                    GObject.idle_add(self.__on_img_building_result_pixbuf,
                                     builder, factor, original_width, img, boxes))
        self.workers['img_builder'].connect('img-building-result-stock',
                lambda builder, img: \
                    GObject.idle_add(self.__on_img_building_result_stock, img))

        self.workers['label_updater'].connect('label-updating-start',
                lambda updater: \
                    GObject.idle_add(self.__on_label_updating_start_cb,
                                     updater))
        self.workers['label_updater'].connect('label-updating-doc-updated',
                lambda updater, progression, doc_name: \
                    GObject.idle_add(self.__on_label_updating_doc_updated_cb,
                                     updater, progression, doc_name))
        self.workers['label_updater'].connect('label-updating-end',
                lambda updater: \
                    GObject.idle_add(self.__on_label_updating_end_cb,
                                     updater))

        self.workers['label_deleter'].connect('label-deletion-start',
                lambda deleter: \
                    GObject.idle_add(self.__on_label_updating_start_cb,
                                     deleter))
        self.workers['label_deleter'].connect('label-deletion-doc-updated',
                lambda deleter, progression, doc_name: \
                    GObject.idle_add(self.__on_label_deletion_doc_updated_cb,
                                     deleter, progression, doc_name))
        self.workers['label_deleter'].connect('label-deletion-end',
                lambda deleter: \
                    GObject.idle_add(self.__on_label_updating_end_cb,
                                     deleter))

        self.workers['ocr_redoer'].connect('redo-ocr-start',
                lambda ocr_redoer: \
                    GObject.idle_add(self.__on_redo_ocr_start_cb,
                                     ocr_redoer))
        self.workers['ocr_redoer'].connect('redo-ocr-doc-updated',
                lambda ocr_redoer, progression, doc_name: \
                    GObject.idle_add(self.__on_redo_ocr_doc_updated_cb,
                                     ocr_redoer, progression, doc_name))
        self.workers['ocr_redoer'].connect('redo-ocr-end',
                lambda ocr_redoer: \
                    GObject.idle_add(self.__on_redo_ocr_end_cb,
                                     ocr_redoer))

        self.workers['single_scan'].connect('single-scan-start',
                lambda worker: \
                    GObject.idle_add(self.__on_single_scan_start, worker))
        self.workers['single_scan'].connect('single-scan-ocr',
                lambda worker: \
                    GObject.idle_add(self.__on_single_scan_ocr, worker))
        self.workers['single_scan'].connect('single-scan-done',
                lambda worker, page: \
                    GObject.idle_add(self.__on_single_scan_done, worker, page))

        self.workers['importer'].connect('import-start',
                lambda worker: \
                    GObject.idle_add(self.__on_import_start, worker))
        self.workers['importer'].connect('import-done',
                lambda worker, doc, page: \
                    GObject.idle_add(self.__on_import_done, worker, doc, page))

        self.workers['export_previewer'].connect('export-preview-start',
                lambda worker: \
                    GObject.idle_add(self.__on_export_preview_start))
        self.workers['export_previewer'].connect('export-preview-done',
                lambda worker, size, pixbuf: \
                    GObject.idle_add(self.__on_export_preview_done, size,
                                     pixbuf))

        self.img['image'].connect_after('draw', self.__on_img_draw)

        self.img['viewport']['widget'].connect("size-allocate",
                                               self.__on_img_resize_cb)

        self.window.set_visible(True)

    def set_search_availability(self, enabled):
        for list_view in self.doc_browsing.values():
            list_view.set_sensitive(enabled)

    def set_mouse_cursor(self, cursor):
        offset = {
            "Normal" : -1,
            "Busy" : 1
        }[cursor]

        self.__busy_mouse_counter += offset
        assert(self.__busy_mouse_counter >= 0)

        if self.__busy_mouse_counter > 0:
            cursor = Gdk.Cursor.new(Gdk.CursorType.WATCH)
        else:
            cursor = None
        self.window.get_window().set_cursor(cursor)

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

    def __on_search_result_cb(self, documents, suggestions):
        self.workers['doc_thumbnailer'].stop()

        print "Got %d suggestions" % len(suggestions)
        self.lists['suggestions']['model'].clear()
        for suggestion in suggestions:
            self.lists['suggestions']['model'].append([suggestion])

        print "Git %d documents" % len(documents)
        self.lists['matches']['model'].clear()
        active_idx = -1
        idx = 0
        for doc in documents:
            if doc == self.doc:
                active_idx = idx
            idx += 1
            self.lists['matches']['model'].append(
                self.__get_doc_model_line(doc))

        if len(documents) > 0 and documents[0].is_new and self.doc.is_new:
            active_idx = 0

        self.lists['matches']['doclist'] = documents
        self.lists['matches']['active_idx'] = active_idx

        self.__select_doc(active_idx)

        self.workers['doc_thumbnailer'].start()


    def __on_page_thumbnailing_start_cb(self, src):
        self.set_progression(src, 0.0, _("Loading thumbnails ..."))
        self.set_mouse_cursor("Busy")

    def __on_page_thumbnailing_page_done_cb(self, src, page_idx, thumbnail):
        line_iter = self.lists['pages']['model'].get_iter(page_idx)
        self.lists['pages']['model'].set_value(line_iter, 0, thumbnail)
        self.set_progression(src, ((float)(page_idx+1) / self.doc.nb_pages),
                             _("Loading thumbnails ..."))

    def __on_page_thumbnailing_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")

    def __on_doc_thumbnailing_start_cb(self, src):
        self.set_progression(src, 0.0, _("Loading thumbnails ..."))
        self.set_mouse_cursor("Busy")

    def __on_doc_thumbnailing_doc_done_cb(self, src, doc_idx, thumbnail):
        line_iter = self.lists['matches']['model'].get_iter(doc_idx)
        self.lists['matches']['model'].set_value(line_iter, 2, thumbnail)
        self.set_progression(src, ((float)(doc_idx+1) /
                                   len(self.lists['matches']['doclist'])),
                             _("Loading thumbnails ..."))
        active_doc_idx = self.lists['matches']['active_idx']
        if active_doc_idx == doc_idx:
            path = Gtk.TreePath(active_doc_idx)
            GObject.idle_add(self.lists['matches']['gui'].scroll_to_path,
                             path, False, 0.0, 0.0)

    def __on_doc_thumbnailing_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")

    def __on_img_building_start(self):
        self.img['boxes']['all'] = []
        self.img['boxes']['highlighted'] = []
        self.img['boxes']['visible'] = []

        self.set_mouse_cursor("Busy")
        self.img['image'].set_from_stock(Gtk.STOCK_EXECUTE, Gtk.IconSize.DIALOG)

    def __on_img_building_result_stock(self, img):
        self.img['image'].set_from_stock(img, Gtk.IconSize.DIALOG)
        self.set_mouse_cursor("Normal")

    def __on_img_building_result_pixbuf(self, builder, factor, original_width,
                                        pixbuf, boxes):
        self.img['boxes']['all'] = boxes
        self.__reload_boxes()

        self.img['factor'] = factor
        self.img['pixbuf'] = pixbuf
        self.img['original_width'] = original_width

        self.img['image'].set_from_pixbuf(pixbuf)
        self.set_mouse_cursor("Normal")

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
        self.workers['reindex'].stop()
        self.workers['reindex'].start()

    def __on_redo_ocr_start_cb(self, src):
        self.set_search_availability(False)
        self.set_mouse_cursor("Busy")
        self.set_progression(src, 0.0, _("Redoing OCR ..."))

    def __on_redo_ocr_doc_updated_cb(self, src, progression, doc_name):
        self.set_progression(src, progression,
                             _("Redoing OCR (%s) ...") % (doc_name))

    def __on_redo_ocr_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")
        self.refresh_label_list()
        # in case the keywords were highlighted
        self.show_page(self.page)
        self.workers['reindex'].stop()
        self.workers['reindex'].start()

    def __on_single_scan_start(self, src):
        self.set_progression(src, 0.0, _("Scanning ..."))
        self.set_mouse_cursor("Busy")
        self.img['image'].set_from_stock(Gtk.STOCK_EXECUTE, Gtk.IconSize.DIALOG)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(False)
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
        self.__config.scan_time['ocr'] = scan_stop - self.__scan_start

        for widget in self.need_doc_widgets:
            widget.set_sensitive(True)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(True)

        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")
        self.refresh_page_list()
    
        assert(page is not None)
        self.show_page(page)

        self.append_docs([self.doc])

        self.workers['progress_updater'].stop()

    def __on_import_start(self, src):
        self.set_progression(src, 0.0, _("Importing ..."))
        self.set_mouse_cursor("Busy")
        self.img['image'].set_from_stock(Gtk.STOCK_EXECUTE, Gtk.IconSize.DIALOG)
        self.workers['progress_updater'].start(
            value_min=0.0, value_max=1.0,
            total_time=self.__config.scan_time['ocr'])
        self.__scan_start = time.time()

    def __on_import_done(self, src, doc, page=None):
        scan_stop = time.time()
        self.workers['progress_updater'].stop()
        # Note: don't update scan time here : OCR is not required for all
        # imports

        for widget in self.need_doc_widgets:
            widget.set_sensitive(True)

        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")
        self.show_doc(doc)  # will refresh the page list
        # Many documents may have been imported actually. So we still
        # refresh the whole list
        self.refresh_doc_list()
        if page != None:
            self.show_page(page)

    def __popup_menu_cb(self, ev_component, event, ui_component, popup_menu):
        # we are only interested in right clicks
        if event.button != 3 or event.type != Gdk.EventType.BUTTON_PRESS:
            return
        popup_menu.popup(None, None, None, None, event.button, event.time)

    def __on_img_mouse_motion(self, event_box, event):
        (mouse_x, mouse_y) = event.get_coords()

        # prevent looking for boxes all the time
        # XXX(Jflesch): This is a hack .. it may have visible side effects
        # in the GUI ...
        now = time.time()
        if (now - self.__last_highlight_update <= 0.05):
            return
        self.__last_highlight_update = now

        to_refresh = self.img['boxes']['selected']
        selected = None

        for box in self.img['boxes']['all']:
            ((a, b), (c, d)) = \
                    self.__get_box_position(box,
                                            window=self.img['image'],
                                            width=0)
            if (mouse_x < a or mouse_y < b
                or mouse_x > c or mouse_y > d):
                continue
            selected = box
            break

        if selected is not None:
            if selected in self.img['boxes']['selected']:
                return
            to_refresh.append(selected)

        if selected is not None:
            self.img['boxes']['selected'] = [selected]
            self.img['image'].set_tooltip_text(selected.content)
        else:
            self.img['boxes']['selected'] = []
            self.img['image'].set_has_tooltip(False)

        for box in to_refresh:
            position = self.__get_box_position(box,
                            window=self.img['image'], width=5)
            self.img['image'].queue_draw_area(position[0][0], position[0][1],
                                             position[1][0] - position[0][0],
                                             position[1][1] - position[0][1])

    def __get_box_position(self, box, window=None, width=1):
        ((a, b), (c, d)) = box.position
        a *= self.img['factor']
        b *= self.img['factor']
        c *= self.img['factor']
        d *= self.img['factor']
        if window:
            (win_w, win_h) = (window.get_allocation().width,
                              window.get_allocation().height)
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

    def __on_img_draw(self, imgwidget, cairo_context):
        for ((color_r, color_b, color_g), line_width, boxes) in [
                ((0.421875, 0.36328125, 0.81640625), 1, self.img['boxes']['visible']),
                ((0.421875, 0.36328125, 0.81640625), 2,
                    self.img['boxes']['selected']),
                ((0.0, 0.62109375, 0.0), 2, self.img['boxes']['highlighted'])
            ]:
            cairo_context.set_source_rgb(color_r, color_b, color_g)
            cairo_context.set_line_width(line_width)

            for box in boxes:
                ((a, b), (c, d)) = self.__get_box_position(box, imgwidget,
                                                           width=line_width)
                cairo_context.rectangle(a, b, c-a, d-b)
                cairo_context.stroke()

    @staticmethod
    def __get_doc_txt(doc):
        labels = doc.labels
        final_str = "%s" % (doc.name)
        nb_pages = doc.nb_pages
        if nb_pages > 1:
            final_str += (_("\n  %d pages") % (doc.nb_pages))
        if len(labels) > 0:
            final_str += ("\n  "
                    + "\n  ".join([x.get_html() for x in labels]))
        return final_str

    def __get_doc_model_line(self, doc):
        doc_txt = self.__get_doc_txt(doc)
        stock = Gtk.STOCK_EXECUTE
        if doc.nb_pages <= 0:
            stock = None
        return ([
            doc_txt,
            doc,
            None,
            stock,
            Gtk.IconSize.DIALOG,
        ])

    def __select_doc(self, doc_idx):
        if doc_idx >= 0:
            # we are going to select the current page in the list
            # except we don't want to be called again because of it
            self.actions['open_doc'][1].enabled = False

            self.lists['matches']['gui'].unselect_all()
            self.lists['matches']['gui'].select_path(Gtk.TreePath(doc_idx))

            self.actions['open_doc'][1].enabled = True

            # HACK(Jflesch): The Gtk documentation says that scroll_to_cell()
            # should do nothing if the target cell is already visible (which
            # is the desired behavior here). Except we just emptied the
            # document list model and remade it from scratch. For some reason,
            # it seems that  Gtk will then always consider that the cell is
            # not visible and move the scrollbar.
            # --> we use idle_add to move the scrollbar only once everything has
            # been displayed
            path = Gtk.TreePath(doc_idx)
            GObject.idle_add(self.lists['matches']['gui'].scroll_to_path,
                             path, False, 0.0, 0.0)
        else:
            self.lists['matches']['gui'].unselect_all()

    def __insert_new_doc(self):
        sentence = unicode(self.search_field.get_text(), encoding='utf-8')
        print "Search: %s" % (sentence.encode('ascii', 'replace'))

        doc_list = self.lists['matches']['doclist']

        # When a scan is done, we try to refresh only the current document.
        # However, the current document may be "New document". In which case
        # it won't appear as "New document" anymore. So we have to add a new
        # one to the list
        if sentence == u"" and (len(doc_list) == 0 or not doc_list[0].is_new):
            # append a new document to the list
            new_doc = ImgDoc(self.__config.workdir)
            doc_list.insert(0, new_doc)
            new_doc_line = self.__get_doc_model_line(new_doc)
            self.lists['matches']['model'].insert(0, new_doc_line)
            return True
        return False

    def append_docs(self, docs):
        # We don't stop the doc thumbnailer here. It might be
        # refreshing other documents we won't
        self.workers['doc_thumbnailer'].wait()

        doc_list = self.lists['matches']['doclist']
        model = self.lists['matches']['model']

        if (len(doc_list) > 0
            and (doc_list[0] in docs or doc_list[0].is_new)):
            # Remove temporarily "New document" from the list
            doc_list.pop(0)
            model.remove(model[0].iter)

        for doc in docs:
            if doc in doc_list:
                # already in the list --> won't append
                docs.remove(doc)

        if len(docs) <= 0:
            return

        active_idx = -1
        for doc in docs:
            if doc == self.doc:
                active_idx = 0
            elif active_idx >= 0:
                active_idx += 1
            doc_list.insert(0, doc)
            doc_line = self.__get_doc_model_line(doc)
            model.insert(0, doc_line)

        max_thumbnail_idx = len(docs)
        if self.__insert_new_doc():
            if active_idx >= 0:
                active_idx += 1
            max_thumbnail_idx += 1

        if active_idx >= 0:
            self.__select_doc(active_idx)

        self.workers['doc_thumbnailer'].start(
            doc_indexes=range(0, max_thumbnail_idx))

    def refresh_docs(self, docs):
        """
        Refresh specific documents in the document list

        Arguments:
            docs --- Array of Doc
        """
        # We don't stop the doc thumbnailer here. It might be
        # refreshing other documents we won't
        self.workers['doc_thumbnailer'].wait()

        doc_list = self.lists['matches']['doclist']

        self.__insert_new_doc()

        doc_indexes = []
        active_idx = -1

        for doc in docs:
            try:
                doc_idx = doc_list.index(doc)
            except ValueError, err:
                print ("Warning: Should refresh doc %s in doc list, but"
                       " didn't find it !" % str(doc))
                continue
            doc_indexes.append(doc_idx)
            if self.doc == doc:
                active_idx = doc_idx
            doc_txt = self.__get_doc_txt(doc)
            doc_line = self.__get_doc_model_line(doc)
            self.lists['matches']['model'][doc_idx] = doc_line

        if active_idx >= 0:
            self.__select_doc(active_idx)

        self.workers['doc_thumbnailer'].start(doc_indexes=doc_indexes)

    def refresh_doc_list(self, docs=[]):
        """
        Update the suggestions list and the matching documents list based on
        the keywords typed by the user in the search field.
        Warning: Will reset all the thumbnail to the default one
        """
        self.workers['doc_thumbnailer'].soft_stop()
        self.workers['searcher'].soft_stop()
        self.workers['searcher'].start()

    def refresh_page_list(self):
        """
        Reload and refresh the page list.
        Warning: Will remove the thumbnails on all the pages
        """
        self.workers['page_thumbnailer'].stop()
        self.lists['pages']['model'].clear()
        for page in self.doc.pages:
            self.lists['pages']['model'].append([
                None,  # no thumbnail
                Gtk.STOCK_EXECUTE,
                Gtk.IconSize.DIALOG,
                _('Page %d') % (page.page_nb + 1),
                page.page_nb
            ])
        self.indicators['total_pages'].set_text(
                _("/ %d") % (self.doc.nb_pages))
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(self.doc.can_edit)
        for widget in self.need_page_widgets:
            widget.set_sensitive(False)
        self.workers['page_thumbnailer'].start()

    def refresh_label_list(self):
        """
        Reload and refresh the label list
        """
        self.lists['labels']['model'].clear()
        labels = self.doc.labels
        for label in self.docsearch.label_list:
            self.lists['labels']['model'].append([
                label.get_html(),
                (label in labels),
                label,
                True
            ])
        for widget in self.need_label_widgets:
            widget.set_sensitive(False)

    def __reload_boxes(self):
        search = unicode(self.search_field.get_text(), encoding='utf-8')
        self.img['boxes']['highlighted'] = self.page.get_boxes(search)
        if self.show_all_boxes.get_active():
            self.img['boxes']['visible'] = self.img['boxes']['all']
        else:
            self.img['boxes']['visible'] = []

    def refresh_page(self):
        self.__reload_boxes()
        self.img['image'].queue_draw()

    def show_page(self, page):
        print "Showing page %s" % (str(page))

        self.workers['img_builder'].stop()

        for widget in self.need_page_widgets:
            widget.set_sensitive(True)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(self.doc.can_edit)

        if page.page_nb >= 0:
            # we are going to select the current page in the list
            # except we don't want to be called again because of it
            self.actions['open_page'][1].enabled = False
            path = Gtk.TreePath(page.page_nb)
            self.lists['pages']['gui'].select_path(path)
            self.lists['pages']['gui'].scroll_to_path(path, False, 0.0, 0.0)
            self.actions['open_page'][1].enabled = True

        # we are going to update the page number
        # except we don't want to be called again because of this update
        self.actions['set_current_page'][1].enabled = False
        self.indicators['current_page'].set_text("%d" % (page.page_nb + 1))
        self.actions['set_current_page'][1].enabled = True

        self.page = page

        self.export['dialog'].set_visible(False)

        self.workers['img_builder'].start()

    def show_doc(self, doc):
        self.doc = doc
        for widget in self.need_doc_widgets:
            widget.set_sensitive(True)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(self.doc.can_edit)
        self.refresh_page_list()
        self.refresh_label_list()
        if self.doc.nb_pages > 0:
            self.show_page(self.doc.pages[0])
        else:
            self.img['image'].set_from_stock(Gtk.STOCK_MISSING_IMAGE,
                                             Gtk.IconSize.DIALOG)

    def __on_export_preview_start(self):
        self.export['estimated_size'].set_text(_("Computing ..."))

    def __on_export_preview_done(self, img_size, pixbuf):
        self.export['estimated_size'].set_text(sizeof_fmt(img_size))
        self.img['image'].set_from_pixbuf(pixbuf)

    def __get_img_area_width(self):
        return self.img['viewport']['widget'].get_allocation().width

    def get_zoom_factor(self, pixbuf_width=None):
        el_idx = self.lists['zoom_levels']['gui'].get_active()
        el_iter = self.lists['zoom_levels']['model'].get_iter(el_idx)
        factor = self.lists['zoom_levels']['model'].get_value(el_iter, 1)
        if factor != 0.0:
            return factor
        wanted_width = self.__get_img_area_width()
        if pixbuf_width == None:
            pixbuf_width = self.img['original_width']
        return float(wanted_width) / pixbuf_width

    def refresh_export_preview(self):
        self.img['image'].set_from_stock(Gtk.STOCK_EXECUTE, Gtk.IconSize.DIALOG)
        self.workers['export_previewer'].stop()
        self.workers['export_previewer'].start()

    def __on_img_resize_cb(self, viewport, rectangle):
        old_size = self.img['viewport']['size']
        new_size = (rectangle.width, rectangle.height)
        if old_size == new_size:
            return

        self.workers['img_builder'].soft_stop()
        self.img['viewport']['size'] = new_size
        print ("Image view port resized. (%d, %d) --> (%d, %d)"
               % (old_size[0], old_size[1], new_size[0], new_size[1]))
        
        # check if zoom level is set to adjusted, if yes,
        # we must resize the image
        el_idx = self.lists['zoom_levels']['gui'].get_active()
        el_iter = self.lists['zoom_levels']['model'].get_iter(el_idx)
        factor = self.lists['zoom_levels']['model'].get_value(el_iter, 1)
        if factor != 0.0:
            return

        self.workers['img_builder'].start()
