#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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
import datetime
import gc
import os
import sys
import threading

import PIL.Image
import gettext
import logging
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from paperwork.frontend.aboutdialog import AboutDialog
from paperwork.frontend.labeleditor import LabelEditor
from paperwork.frontend.widgets import LabelColorButton
from paperwork.frontend.mainwindow.pages import PageDrawer
from paperwork.frontend.mainwindow.pages import JobFactoryPageBoxesLoader
from paperwork.frontend.mainwindow.pages import JobFactoryPageImgLoader
from paperwork.frontend.mainwindow.scan import ScanWorkflow
from paperwork.frontend.mainwindow.scan import MultiAnglesScanWorkflowDrawer
from paperwork.frontend.mainwindow.scan import SingleAngleScanWorkflowDrawer
from paperwork.frontend.multiscan import MultiscanDialog
from paperwork.frontend.pageeditor import PageEditingDialog
from paperwork.frontend.searchdialog import SearchDialog
from paperwork.frontend.settingswindow import SettingsWindow
from paperwork.frontend.util import load_cssfile
from paperwork.frontend.util import load_uifile
from paperwork.frontend.util import sizeof_fmt
from paperwork.frontend.util.actions import SimpleAction
from paperwork.frontend.util.config import get_scanner
from paperwork.frontend.util.dialog import ask_confirmation
from paperwork.frontend.util.dialog import popup_no_scanner_found
from paperwork.frontend.util.img import add_img_border
from paperwork.frontend.util.img import image2pixbuf
from paperwork.frontend.util.canvas import Canvas
from paperwork.frontend.util.canvas.animations import SpinnerAnimation
from paperwork.frontend.util.canvas.drawers import PillowImageDrawer
from paperwork.frontend.util.canvas.drawers import ProgressBarDrawer
from paperwork.frontend.util.jobs import Job, JobFactory, JobScheduler
from paperwork.frontend.util.renderer import LabelWidget
from paperwork.backend import docimport
from paperwork.backend.common.doc import BasicDoc
from paperwork.backend.common.page import BasicPage, DummyPage
from paperwork.backend.docsearch import DocSearch
from paperwork.backend.docsearch import DummyDocSearch
from paperwork.backend.img.doc import ImgDoc
from paperwork.backend.labels import Label

_ = gettext.gettext
logger = logging.getLogger(__name__)


def check_scanner(main_win, config):
    if config['scanner_devid'].value is not None:
        return True
    main_win.actions['open_settings'][1].do()
    return False


def sort_documents_by_date(documents):
    documents.sort()
    documents.reverse()


def set_widget_state(widgets, state, cond=lambda widget: True):
    for widget in widgets:
        if cond(widget):
            if isinstance(widget, Gio.Action):
                widget.set_enabled(state)
            else:
                widget.set_sensitive(state)


class JobIndexLoader(Job):
    """
    Reload the doc index
    """

    __gsignals__ = {
        'index-loading-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'index-loading-progression': (GObject.SignalFlags.RUN_LAST, None,
                                      (GObject.TYPE_FLOAT,
                                       GObject.TYPE_STRING)),
        'index-loading-end': (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_PYOBJECT, )),
    }

    can_stop = True
    priority = 100

    def __init__(self, factory, job_id, config):
        Job.__init__(self, factory, job_id)
        self.__config = config
        self.started = False
        self.done = False

    def __progress_cb(self, progression, total, step, doc=None):
        """
        Update the main progress bar
        """
        if not self.can_run:
            raise StopIteration()
        if progression % 50 != 0:
            return
        txt = None
        if step == DocSearch.INDEX_STEP_LOADING:
            txt = _('Loading ...')
        else:
            assert()  # unknown progression type
            txt = ""
        if doc is not None:
            txt += (" (%s)" % (doc.name))
        self.emit('index-loading-progression', float(progression) / total, txt)

    def do(self):
        if self.done:
            return
        self.can_run = True
        if not self.started:
            self.emit('index-loading-start')
            self.started = True
        try:
            docsearch = DocSearch(self.__config['workdir'].value,
                                  self.__progress_cb)
            if not self.can_run:
                return
            self.emit('index-loading-end', docsearch)
            self.done = True
        except StopIteration:
            logger.info("Index loading interrupted")

    def stop(self, will_resume=False):
        if not will_resume and not self.done:
            self.emit('index-loading-end', None)
            self.done = True
        self.can_run = False


GObject.type_register(JobIndexLoader)


class JobFactoryIndexLoader(JobFactory):
    def __init__(self, main_window, config):
        JobFactory.__init__(self, "IndexLoader")
        self.__main_window = main_window
        self.__config = config

    def make(self):
        job = JobIndexLoader(self, next(self.id_generator), self.__config)
        job.connect('index-loading-start',
                    lambda job: GLib.idle_add(
                        self.__main_window.on_index_loading_start_cb, job))
        job.connect('index-loading-progression',
                    lambda job, progression, txt:
                    GLib.idle_add(self.__main_window.set_progression,
                                  job, progression, txt))
        job.connect('index-loading-end',
                    lambda loader, docsearch: GLib.idle_add(
                        self.__main_window.on_index_loading_end_cb, loader,
                        docsearch
                    ))
        return job


class JobDocExaminer(Job):
    """
    Look for modified documents
    """

    __gsignals__ = {
        'doc-examination-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'doc-examination-progression': (GObject.SignalFlags.RUN_LAST, None,
                                        (GObject.TYPE_FLOAT,
                                         GObject.TYPE_STRING)),
        'doc-examination-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 50

    def __init__(self, factory, id, config, docsearch):
        Job.__init__(self, factory, id)
        self.__config = config
        self.docsearch = docsearch
        self.done = False
        self.started = False

    def __progress_cb(self, progression, total, step, doc=None):
        """
        Update the main progress bar
        """
        if not self.can_run:
            raise StopIteration()
        if progression % 10 != 0:
            return
        txt = None
        if step == DocSearch.INDEX_STEP_CHECKING:
            txt = _('Checking ...')
        else:
            assert()  # unknown progression type
            txt = ""
        if doc is not None:
            txt += (" (%s)" % (str(doc)))
        self.emit('doc-examination-progression',
                  float(progression) / total, txt)

    def do(self):
        if self.done:
            return

        self.can_run = True

        if not self.started:
            self.emit('doc-examination-start')
            self.started = True
        self.new_docs = set()  # documents
        self.docs_changed = set()  # documents
        self.docs_missing = set()  # document ids
        try:
            doc_examiner = self.docsearch.get_doc_examiner()
            doc_examiner.examine_rootdir(
                self.__on_new_doc,
                self.__on_doc_changed,
                self.__on_doc_missing,
                self.__progress_cb)
            self.emit('doc-examination-end')
            self.done = True
        except StopIteration:
            logger.info("Document examination interrupted")

    def stop(self, will_resume=False):
        self.can_run = False
        if not will_resume:
            self.emit('doc-examination-end')

    def __on_new_doc(self, doc):
        self.new_docs.add(doc)

    def __on_doc_changed(self, doc):
        self.docs_changed.add(doc)

    def __on_doc_missing(self, docid):
        self.docs_missing.add(docid)


GObject.type_register(JobDocExaminer)


class JobFactoryDocExaminer(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "DocExaminer")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch):
        job = JobDocExaminer(self, next(self.id_generator),
                             self.__config, docsearch)
        job.connect(
            'doc-examination-start',
            lambda job: GLib.idle_add(
                self.__main_win.on_doc_examination_start_cb, job))
        job.connect(
            'doc-examination-progression',
            lambda job, progression, txt: GLib.idle_add(
                self.__main_win.set_progression, job, progression, txt))
        job.connect(
            'doc-examination-end',
            lambda job: GLib.idle_add(
                self.__main_win.on_doc_examination_end_cb, job))
        return job


class JobIndexUpdater(Job):
    """
    Update the index
    """

    __gsignals__ = {
        'index-update-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'index-update-progression': (GObject.SignalFlags.RUN_LAST, None,
                                     (GObject.TYPE_FLOAT,
                                      GObject.TYPE_STRING)),
        'index-update-interrupted': (GObject.SignalFlags.RUN_LAST, None, ()),
        'index-update-write': (GObject.SignalFlags.RUN_LAST, None, ()),
        'index-update-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = True
    priority = 15

    def __init__(self, factory, id, config, docsearch,
                 new_docs=set(), upd_docs=set(), del_docs=set(),
                 optimize=True):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__config = config

        self.__condition = threading.Condition()

        self.new_docs = new_docs
        self.upd_docs = upd_docs
        self.del_docs = del_docs
        self.optimize = optimize
        self.index_updater = None
        self.total = (len(self.new_docs) + len(self.upd_docs)
                      + len(self.del_docs))
        self.progression = float(0)

    def __wakeup(self):
        self.__condition.acquire()
        self.__condition.notify_all()
        self.__condition.release()

    def __wait(self):
        # HACK(Jflesch): Make sure the signal is actually taken care
        # of before continuing. Otherwise, on slow computers, the
        # progress bar may not be updated at all until the index
        # update is finished
        self.__condition.acquire()
        GLib.idle_add(self.__wakeup)
        self.__condition.wait()
        self.__condition.release()

    def do(self):
        # keep in mind that we may have been interrupted and then called back
        # later

        self.can_run = True

        total = len(self.new_docs) + len(self.upd_docs) + len(self.del_docs)
        if total <= 0 and not self.optimize and self.index_updater is None:
            return

        if self.index_updater is None:
            self.emit('index-update-start')
            self.index_updater = self.__docsearch.get_index_updater(
                optimize=self.optimize)

        if not self.can_run:
            self.emit('index-update-interrupted')
            return

        docs = [
            (_("Indexing new document ..."), self.new_docs,
             self.index_updater.add_doc),
            (_("Reindexing modified document ..."), self.upd_docs,
             self.index_updater.upd_doc),
            (_("Removing deleted document from index ..."), self.del_docs,
             self.index_updater.del_doc),
        ]

        for (op_name, doc_bunch, op) in docs:
            try:
                while True:
                    if not self.can_run:
                        self.emit('index-update-interrupted')
                        return
                    doc = doc_bunch.pop()
                    self.emit('index-update-progression',
                              (self.progression * 0.75) / self.total,
                              "%s (%s)" % (op_name, str(doc)))
                    self.__wait()
                    op(doc)
                    self.progression += 1
            except KeyError:
                pass

        if not self.can_run:
            self.emit('index-update-interrupted')
            return

        self.emit('index-update-progression', 0.75,
                  _("Writing index ..."))
        self.emit('index-update-write')
        self.__wait()
        self.index_updater.commit()
        self.index_updater = None
        self.optimize = False
        self.emit('index-update-progression', 1.0, "")
        self.emit('index-update-end')

    def stop(self, will_resume=False):
        self.can_run = False
        if not will_resume:
            self.connect('index-update-interrupted',
                         lambda job:
                         GLib.idle_add(self.index_updater.cancel))


GObject.type_register(JobIndexUpdater)


class JobFactoryIndexUpdater(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "IndexUpdater")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch,
             new_docs=set(), upd_docs=set(), del_docs=set(),
             optimize=True, reload_list=False):
        job = JobIndexUpdater(self, next(self.id_generator), self.__config,
                              docsearch, new_docs, upd_docs, del_docs,
                              optimize)
        job.connect('index-update-start',
                    lambda updater:
                    GLib.idle_add(self.__main_win.on_index_update_start_cb,
                                  updater))
        job.connect('index-update-progression',
                    lambda updater, progression, txt:
                    GLib.idle_add(self.__main_win.set_progression, updater,
                                  progression, txt))
        job.connect('index-update-write',
                    lambda updater:
                    GLib.idle_add(self.__main_win.on_index_update_write_cb,
                                  updater))
        job.connect('index-update-end',
                    lambda updater:
                    GLib.idle_add(self.__main_win.on_index_update_end_cb,
                                  updater))
        if reload_list:
            job.connect('index-update-end',
                        lambda updater:
                        GLib.idle_add(self.__main_win.refresh_doc_list))
        return job


class JobDocSearcher(Job):
    """
    Search the documents
    """

    __gsignals__ = {
        'search-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        # user made a typo
        'search-invalid': (GObject.SignalFlags.RUN_LAST, None, ()),
        # array of documents
        'search-results': (GObject.SignalFlags.RUN_LAST, None,
                           # XXX(Jflesch): TYPE_STRING would turn the Unicode
                           # object into a string object
                           (GObject.TYPE_PYOBJECT,
                            GObject.TYPE_PYOBJECT,)),
        # array of suggestions
        'search-suggestions': (GObject.SignalFlags.RUN_LAST, None,
                               (GObject.TYPE_PYOBJECT,)),
    }

    can_stop = True
    priority = 500

    def __init__(self, factory, id, config, docsearch, sort_func, search):
        Job.__init__(self, factory, id)
        self.search = search
        self.__docsearch = docsearch
        self.__sort_func = sort_func
        self.__config = config

    def do(self):
        self.can_run = True

        self._wait(0.5)
        if not self.can_run:
            return

        self.emit('search-start')

        try:
            logger.info("Searching: [%s]" % self.search)
            documents = self.__docsearch.find_documents(self.search)
        except Exception, exc:
            logger.error("Invalid search: [%s]" % self.search)
            logger.error("Exception was: %s: %s" % (type(exc), str(exc)))
            self.emit('search-invalid')
            return
        if not self.can_run:
            return

        if self.search == u"":
            # when no specific search has been done, the sorting is always
            # the same
            sort_documents_by_date(documents)
        else:
            self.__sort_func(documents)
        if not self.can_run:
            return
        self.emit('search-results', self.search, documents)

        suggestions = self.__docsearch.find_suggestions(self.search)
        if not self.can_run:
            return
        self.emit('search-suggestions', suggestions)

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobDocSearcher)


class JobFactoryDocSearcher(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "Search")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch, sort_func, search_sentence):
        job = JobDocSearcher(self, next(self.id_generator), self.__config,
                             docsearch, sort_func, search_sentence)
        job.connect('search-start', lambda searcher:
                    GLib.idle_add(self.__main_win.on_search_start_cb))
        job.connect('search-results',
                    lambda searcher, search, documents:
                    GLib.idle_add(self.__main_win.on_search_results_cb,
                                  search, documents))
        job.connect('search-invalid',
                    lambda searcher: GLib.idle_add(
                        self.__main_win.on_search_invalid_cb))
        job.connect('search-suggestions',
                    lambda searcher, suggestions:
                    GLib.idle_add(self.__main_win.on_search_suggestions_cb,
                                  suggestions))
        return job


class JobLabelPredictor(Job):
    """
    Predicts what labels should be on a document
    """

    __gsignals__ = {
        # array of labels (strings)
        'predicted-labels': (GObject.SignalFlags.RUN_LAST, None,
                             (
                                 GObject.TYPE_PYOBJECT,  # doc
                                 GObject.TYPE_PYOBJECT,  # array of labels
                             )),
    }

    can_stop = True
    priority = 10

    def __init__(self, factory, id, docsearch, doc):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.doc = doc

    def _progress_cb(self, current, total):
        if not self.can_run:
            raise StopIteration()

    def do(self):
        self.can_run = True
        try:
            predicted_labels = self.__docsearch.predict_label_list(
                self.doc, progress_cb=self._progress_cb)
            self.emit('predicted-labels', self.doc, predicted_labels)
        except StopIteration:
            return

    def stop(self, will_resume=False):
        self.can_run = False


GObject.type_register(JobLabelPredictor)


class JobFactoryLabelPredictorOnOpenDoc(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "Label predictor (on opened doc)")
        self.__main_win = main_win

    def make(self, doc):
        job = JobLabelPredictor(self, next(self.id_generator),
                                self.__main_win.docsearch, doc)
        job.connect('predicted-labels',
                    lambda predictor, doc, labels:
                    GLib.idle_add(self.__main_win.on_label_prediction_cb,
                                  doc, labels))
        return job


class JobFactoryLabelPredictorOnNewDoc(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "Label predictor (on new doc)")
        self.__main_win = main_win

    def make(self, doc):
        job = JobLabelPredictor(self, next(self.id_generator),
                                self.__main_win.docsearch, doc)
        return job


class JobDocThumbnailer(Job):
    """
    Generate doc list thumbnails
    """

    THUMB_BORDER = 1

    __gsignals__ = {
        'doc-thumbnailing-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'doc-thumbnailing-doc-done': (GObject.SignalFlags.RUN_LAST, None,
                                      (
                                          GObject.TYPE_PYOBJECT,  # thumbnail
                                          GObject.TYPE_PYOBJECT,  # doc
                                          GObject.TYPE_INT,  # current doc
                                          # number of docs being thumbnailed
                                          GObject.TYPE_INT,)),
        'doc-thumbnailing-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = True
    priority = 20

    def __init__(self, factory, id, doclist):
        Job.__init__(self, factory, id)
        self.__doclist = doclist
        self.__current_idx = -1

    def __resize(self, img):
        (width, height) = img.size
        # always make sure the thumbnail has a specific height
        # otherwise the scrollbar keep moving while loading
        if width > MainWindow.SMALL_THUMBNAIL_WIDTH:
            img = img.crop((0, 0, MainWindow.SMALL_THUMBNAIL_WIDTH, height))
            img = img.copy()
        elif width < MainWindow.SMALL_THUMBNAIL_WIDTH:
            height = min(height, MainWindow.SMALL_THUMBNAIL_HEIGHT)
            new_img = PIL.Image.new(
                'RGBA', (MainWindow.SMALL_THUMBNAIL_WIDTH, height),
                '#FFFFFF'
            )
            w = (MainWindow.SMALL_THUMBNAIL_WIDTH - width) / 2
            new_img.paste(img, (w, 0, w + width, height))
            img = new_img
        return img

    def do(self):
        self.can_run = True
        if self.__current_idx >= len(self.__doclist):
            return
        if not self.can_run:
            return

        if self.__current_idx < 0:
            self.emit('doc-thumbnailing-start')
            self.__current_idx = 0

        for idx in xrange(self.__current_idx, len(self.__doclist)):
            doc = self.__doclist[idx]
            if doc.nb_pages <= 0:
                continue

            # always request the same size, even for small thumbnails
            # so we don't invalidate cache + previous thumbnails
            img = doc.pages[0].get_thumbnail(BasicPage.DEFAULT_THUMB_WIDTH,
                                             BasicPage.DEFAULT_THUMB_HEIGHT)
            if not self.can_run:
                return

            (w, h) = img.size
            factor = max(
                (float(w) / MainWindow.SMALL_THUMBNAIL_WIDTH),
                (float(h) / MainWindow.SMALL_THUMBNAIL_HEIGHT)
            )
            w /= factor
            h /= factor
            img = img.resize((int(w), int(h)), PIL.Image.ANTIALIAS)
            if not self.can_run:
                return

            img = self.__resize(img)
            if not self.can_run:
                return

            img = add_img_border(img, width=self.THUMB_BORDER)
            if not self.can_run:
                return

            pixbuf = image2pixbuf(img)
            self.emit('doc-thumbnailing-doc-done', pixbuf, doc,
                      idx, len(self.__doclist))

            self.__current_idx = idx

        self.emit('doc-thumbnailing-end')

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()
        if not will_resume and self.__current_idx >= 0:
            self.emit('doc-thumbnailing-end')


GObject.type_register(JobDocThumbnailer)


class JobFactoryDocThumbnailer(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "DocThumbnailer")
        self.__main_win = main_win

    def make(self, doclist):
        """
        Arguments:
            doclist --- must be an array of (position, document), position
                        being the position of the document
        """
        job = JobDocThumbnailer(self, next(self.id_generator), doclist)
        job.connect(
            'doc-thumbnailing-start',
            lambda thumbnailer:
            GLib.idle_add(self.__main_win.on_doc_thumbnailing_start_cb,
                          thumbnailer))
        job.connect(
            'doc-thumbnailing-doc-done',
            lambda thumbnailer, thumbnail, doc, doc_nb, total_docs:
            GLib.idle_add(self.__main_win.on_doc_thumbnailing_doc_done_cb,
                          thumbnailer, thumbnail, doc, doc_nb,
                          total_docs))
        job.connect(
            'doc-thumbnailing-end',
            lambda thumbnailer:
            GLib.idle_add(self.__main_win.on_doc_thumbnailing_end_cb,
                          thumbnailer))
        return job


class JobLabelCreator(Job):
    __gsignals__ = {
        'label-creation-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'label-creation-doc-read': (GObject.SignalFlags.RUN_LAST, None,
                                    (GObject.TYPE_FLOAT,
                                     GObject.TYPE_STRING)),
        'label-creation-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 5

    def __init__(self, factory, id, docsearch, new_label, doc):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__new_label = new_label
        self.__doc = doc

    def __progress_cb(self, progression, total, step, doc):
        self.emit('label-creation-doc-read', float(progression) / total,
                  doc.name)

    def do(self):
        self.emit('label-creation-start')
        try:
            self.__docsearch.create_label(self.__new_label, self.__doc,
                                          self.__progress_cb)
        finally:
            self.emit('label-creation-end')


GObject.type_register(JobLabelCreator)


class JobFactoryLabelCreator(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "LabelCreator")
        self.__main_win = main_win

    def make(self, docsearch, new_label, doc):
        job = JobLabelCreator(self, next(self.id_generator), docsearch,
                              new_label, doc)
        job.connect('label-creation-start',
                    lambda updater:
                    GLib.idle_add(
                        self.__main_win.on_label_updating_start_cb,
                        updater))
        job.connect('label-creation-doc-read',
                    lambda updater, progression, doc_name:
                    GLib.idle_add(
                        self.__main_win.on_label_updating_doc_updated_cb,
                        updater, progression, doc_name))
        job.connect('label-creation-end',
                    lambda updater:
                    GLib.idle_add(
                        self.__main_win.on_label_updating_end_cb,
                        updater))
        return job


class JobLabelUpdater(Job):
    __gsignals__ = {
        'label-updating-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'label-updating-doc-updated': (GObject.SignalFlags.RUN_LAST, None,
                                       (GObject.TYPE_FLOAT,
                                        GObject.TYPE_STRING)),
        'label-updating-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 5

    def __init__(self, factory, id, docsearch, old_label, new_label):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__old_label = old_label
        self.__new_label = new_label

    def __progress_cb(self, progression, total, step, doc):
        self.emit('label-updating-doc-updated', float(progression) / total,
                  doc.name)

    def do(self):
        self.emit('label-updating-start')
        try:
            self.__docsearch.update_label(self.__old_label, self.__new_label,
                                          self.__progress_cb)
        finally:
            self.emit('label-updating-end')


GObject.type_register(JobLabelUpdater)


class JobFactoryLabelUpdater(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "LabelUpdater")
        self.__main_win = main_win

    def make(self, docsearch, old_label, new_label):
        job = JobLabelUpdater(self, next(self.id_generator), docsearch,
                              old_label, new_label)
        job.connect('label-updating-start',
                    lambda updater:
                    GLib.idle_add(
                        self.__main_win.on_label_updating_start_cb,
                        updater))
        job.connect('label-updating-doc-updated',
                    lambda updater, progression, doc_name:
                    GLib.idle_add(
                        self.__main_win.on_label_updating_doc_updated_cb,
                        updater, progression, doc_name))
        job.connect('label-updating-end',
                    lambda updater:
                    GLib.idle_add(
                        self.__main_win.on_label_updating_end_cb,
                        updater))
        return job


class JobLabelDeleter(Job):
    __gsignals__ = {
        'label-deletion-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'label-deletion-doc-updated': (GObject.SignalFlags.RUN_LAST, None,
                                       (GObject.TYPE_FLOAT,
                                        GObject.TYPE_STRING)),
        'label-deletion-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 5

    def __init__(self, factory, id, docsearch, label):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__label = label

    def __progress_cb(self, progression, total, step, doc):
        self.emit('label-deletion-doc-updated', float(progression) / total,
                  doc.name)

    def do(self):
        self.emit('label-deletion-start')
        try:
            self.__docsearch.destroy_label(self.__label, self.__progress_cb)
        finally:
            self.emit('label-deletion-end')


GObject.type_register(JobLabelDeleter)


class JobFactoryLabelDeleter(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "LabelDeleter")
        self.__main_win = main_win

    def make(self, docsearch, label):
        job = JobLabelDeleter(self, next(self.id_generator), docsearch, label)
        job.connect('label-deletion-start',
                    lambda deleter:
                    GLib.idle_add(self.__main_win.on_label_updating_start_cb,
                                  deleter))
        job.connect('label-deletion-doc-updated',
                    lambda deleter, progression, doc_name:
                    GLib.idle_add(
                        self.__main_win.on_label_deletion_doc_updated_cb,
                        deleter, progression, doc_name))
        job.connect('label-deletion-end',
                    lambda deleter:
                    GLib.idle_add(self.__main_win.on_label_updating_end_cb,
                                  deleter))
        return job


class JobExportPreviewer(Job):
    __gsignals__ = {
        'export-preview-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'export-preview-done': (GObject.SignalFlags.RUN_LAST, None,
                                (GObject.TYPE_INT, GObject.TYPE_PYOBJECT,)),
    }

    can_stop = True
    priority = 500

    def __init__(self, factory, id, exporter):
        Job.__init__(self, factory, id)
        self.__exporter = exporter

    def do(self):
        self.can_run = True
        self._wait(0.7)
        if not self.can_run:
            return

        self.emit('export-preview-start')

        size = self.__exporter.estimate_size()
        if not self.can_run:
            return

        img = self.__exporter.get_img()
        if not self.can_run:
            return

        drawer = PillowImageDrawer((0, 0), img)
        if not self.can_run:
            return

        self.emit('export-preview-done', size, drawer)

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobExportPreviewer)


class JobFactoryExportPreviewer(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "ExportPreviewer")
        self.__main_win = main_win

    def make(self, exporter):
        job = JobExportPreviewer(self, next(self.id_generator), exporter)
        job.connect('export-preview-start',
                    lambda job:
                    GLib.idle_add(self.__main_win.on_export_preview_start))
        job.connect('export-preview-done',
                    lambda job, size, pixbuf:
                    GLib.idle_add(self.__main_win.on_export_preview_done,
                                  size, pixbuf))
        return job


class JobPageEditor(Job):
    __gsignals__ = {
        'page-editing-img-edit': (GObject.SignalFlags.RUN_LAST, None,
                                  (GObject.TYPE_PYOBJECT, )),
        'page-editing-done': (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_PYOBJECT, )),
    }

    can_stop = False
    priority = 10

    def __init__(self, factory, id, page, changes=[]):
        Job.__init__(self, factory, id)
        self.__page = page
        self.__changes = changes[:]

    def do(self):
        self.emit('page-editing-img-edit', self.__page)
        try:
            img = self.__page.img
            for change in self.__changes:
                img = change.do(img, 1.0)
            self.__page.img = img
        finally:
            self.emit('page-editing-done', self.__page)


GObject.type_register(JobPageEditor)


class JobPageImgRenderer(Job):
    __gsignals__ = {
        'rendered': (GObject.SignalFlags.RUN_LAST, None,
                     (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT)),
    }

    can_stop = False
    priority = 100

    def __init__(self, factory, id, page):
        Job.__init__(self, factory, id)
        self.page = page

    def do(self):
        self.emit("rendered", self.page.img, self.page.boxes)


class JobFactoryPageImgRenderer(JobFactory):
    def __init__(self):
        JobFactory.__init__(self, "PageImgRenderer")

    def make(self, page):
        return JobPageImgRenderer(self, next(self.id_generator), page)


class JobImporter(Job):
    __gsignals__ = {
        'no-doc-imported': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 150

    def __init__(self, factory, id, main_win, config, importer, file_uri):
        Job.__init__(self, factory, id)
        self.__main_win = main_win
        self.__config = config
        self.importer = importer
        self.file_uri = file_uri

    class IndexAdder(object):
        def __init__(self, main_win, page_iterator, must_add_labels=False):
            self._main_win = main_win
            self._page_iterator = page_iterator
            self.must_add_labels = must_add_labels

            self._docs_to_label_predict = set()
            self._docs_to_upd = set()

        def start(self):
            self._ocr_next_page()

        def _ocr_next_page(self):
            try:
                page = next(self._page_iterator)
                logger.info("Examining page %s" % str(page))
            except StopIteration:
                logger.info("OCR has been redone on all the target pages")
                if len(self._docs_to_label_predict) > 0:
                    self._predict_labels()
                else:
                    self._update_index()
                return

            renderer = self._main_win.job_factories['page_img_renderer']
            renderer = renderer.make(page)
            renderer.connect("rendered", lambda _, img, boxes:
                             GLib.idle_add(self._ocr,
                                           page, img, boxes))
            self._main_win.schedulers['main'].schedule(renderer)

        def _ocr(self, page, page_img, boxes):
            if len(boxes) <= 0:
                logger.info("Doing OCR on %s" % str(page))
                self._main_win.show_doc(page.doc)
                scan_workflow = self._main_win.make_scan_workflow()
                drawer = self._main_win.make_scan_workflow_drawer(
                    scan_workflow, single_angle=True, page=page)
                self._main_win.add_scan_workflow(page.doc, drawer,
                                                 page_nb=page.page_nb)
                scan_workflow.connect('process-done',
                                      lambda scan_workflow, img, boxes:
                                      GLib.idle_add(self._on_page_ocr_done,
                                                    scan_workflow, img,
                                                    boxes, page))
                scan_workflow.ocr(page_img, angles=1)
            else:
                logger.info("Imported page %s already has text" % page)
                self._add_doc_to_checklists(page.doc)
                GLib.idle_add(self._ocr_next_page)

        def _on_page_ocr_done(self, scan_workflow, img, boxes, page):
            if page.can_edit:
                page.img = img
            page.boxes = boxes

            logger.info("OCR done on %s" % str(page))
            self._main_win.remove_scan_workflow(scan_workflow)
            self._main_win.show_page(page, force_refresh=True)
            self._add_doc_to_checklists(page.doc)
            self._ocr_next_page()

        def _add_doc_to_checklists(self, doc):
            self._docs_to_upd.add(doc)
            if self.must_add_labels:
                self._docs_to_label_predict.add(doc)

        def _predict_labels(self):
            for doc in self._docs_to_label_predict:
                logger.info("Predicting labels on doc %s"
                            % str(doc))
                factory = self._main_win.job_factories[
                    'label_predictor_on_new_doc'
                ]
                job = factory.make(doc)
                job.connect("predicted-labels",
                            self._on_predicted_labels)
                self._main_win.schedulers['main'].schedule(job)

        def _on_predicted_labels(self, predictor, doc, predicted_labels):
            GLib.idle_add(self._on_predicted_labels2, doc, predicted_labels)

        def _on_predicted_labels2(self, doc, predicted_labels):
            logger.info("Label predicted on doc %s" % str(doc))
            for label in self._main_win.docsearch.label_list:
                if label.name in predicted_labels:
                    self._main_win.docsearch.add_label(doc, label,
                                                       update_index=False)
            self._docs_to_label_predict.remove(doc)
            if len(self._docs_to_label_predict) <= 0:
                self._update_index()

        def _update_index(self):
            logger.info("Updating index for %d docs"
                        % len(self._docs_to_upd))
            job = self._main_win.job_factories['index_updater'].make(
                self._main_win.docsearch, new_docs=self._docs_to_upd,
                optimize=False, reload_list=True)
            self._main_win.schedulers['main'].schedule(job)
            self._docs_to_upd = set()

    def do(self):
        self.__main_win.set_mouse_cursor("Busy")
        (docs, page, must_add_labels) = self.importer.import_doc(
            self.file_uri, self.__config, self.__main_win.docsearch,
            self.__main_win.doc)
        self.__main_win.set_mouse_cursor("Normal")

        if docs is None or len(docs) <= 0:
            self.emit('no-doc-imported')
            return

        if page is not None:
            nb_docs = 0
            nb_pages = 1
        else:
            nb_docs = len(docs)
            nb_pages = 0
        logger.info("Importing %d docs and %d pages" % (nb_docs, nb_pages))

        self.__main_win.show_doc(docs[-1], force_refresh=True)

        if page is not None:
            self.__main_win.show_page(page, force_refresh=True)
        set_widget_state(self.__main_win.need_doc_widgets, True)

        if page is not None:
            self.IndexAdder(self.__main_win, iter([page]),
                            must_add_labels).start()
            return

        if len(docs) > 0:
            pages = []
            for doc in docs:
                new_pages = [p for p in doc.pages]
                pages += new_pages
            if len(pages) > 0:
                self.IndexAdder(self.__main_win, iter(pages),
                                must_add_labels).start()


class JobFactoryImporter(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "Importer")
        self._main_win = main_win
        self._config = config

    def make(self, importer, file_uri):
        return JobImporter(self, next(self.id_generator),
                           self._main_win, self._config,
                           importer, file_uri)


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

        must_insert_new = \
            not self.__main_win.lists['doclist']['model']['has_new']
        if must_insert_new:
            self.__main_win.insert_new_doc()

        doclist = self.__main_win.lists['doclist']['gui']
        row = doclist.get_row_at_index(0)
        doclist.select_row(row)


class ActionOpenSelectedDocument(SimpleAction):
    """
    Starts a new document.
    """
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Open selected document")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)

        doclist = self.__main_win.lists['doclist']['gui']
        row = doclist.get_selected_row()
        if row is None:
            return
        docid = self.__main_win.lists['doclist']['model']['by_row'][row]
        doc = self.__main_win.docsearch.get_doc_from_docid(docid)
        if doc is None:
            # assume new doc
            doc = ImgDoc(self.__config['workdir'].value)

        logger.info("Showing doc %s" % doc)
        if doc.nb_pages <= 1:
            self.__main_win.set_layout('paged', force_refresh=False)
        else:
            self.__main_win.set_layout('grid', force_refresh=False)
        self.__main_win.show_doc(doc)


class ActionUpdateSearchResults(SimpleAction):
    """
    Update search results
    """
    def __init__(self, main_window, refresh_pages=True):
        SimpleAction.__init__(self, "Update search results")
        self.__main_win = main_window
        self.__refresh_pages = refresh_pages

    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_doc_list()

        if self.__refresh_pages:
            # TODO: highlight pages with keywords
            search = unicode(self.__main_win.search_field.get_text(),
                             encoding='utf-8')
            self.__main_win.refresh_boxes()

    def on_icon_press_cb(self, entry, iconpos=Gtk.EntryIconPosition.SECONDARY,
                         event=None):
        if iconpos == Gtk.EntryIconPosition.PRIMARY:
            entry.grab_focus()
        elif Gtk.EntryIconPosition.SECONDARY:
            logger.info("Opening search dialog")
            dialog = SearchDialog(self.__main_win)
            response = dialog.run()
            if response == 1:
                logger.info("Search dialog: apply")
                search = dialog.get_search_string()
                search = search.encode('utf-8')
                self.__main_win.search_field.set_text(search)
            else:
                logger.info("Search dialog: cancelled")


class ActionOpenViewSettings(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open view settings")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.popovers['view_settings'].set_relative_to(
            self.__main_win.actions['open_view_settings'][0][0])
        self.__main_win.popovers['view_settings'].set_visible(True)


class ActionShowDocumentAsPaged(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Show document page per page")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.set_layout('paged')


class ActionShowDocumentAsGrid(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Show document as a grid")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.set_layout('grid')


class ActionSwitchSorting(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Switch sorting")
        self.__main_win = main_window
        self.__config = config
        self.__upd_search_results_action = \
            ActionUpdateSearchResults(main_window, refresh_pages=False)

    def do(self):
        SimpleAction.do(self)
        (sorting_name, unused) = self.__main_win.get_doc_sorting()
        logger.info("Document sorting: %s" % sorting_name)
        self.__config['result_sorting'].value = sorting_name
        self.__config.write()
        self.__upd_search_results_action.do()


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
        self.__main_win.show_page(page, force_refresh=True)


class ActionOpenPageNb(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Show a page (selected on its number)")
        self.__main_win = main_window

    def entry_changed(self, entry):
        pass

    def do(self):
        SimpleAction.do(self)
        page_nb = self.__main_win.page_nb['current'].get_text()
        try:
            page_nb = int(page_nb) - 1
        except ValueError:
            return
        if page_nb < 0 or page_nb > self.__main_win.doc.nb_pages:
            return
        page = self.__main_win.doc.pages[page_nb]
        self.__main_win.show_page(page)


class ActionUpdPageSizes(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Reload current page")
        self.__main_win = main_window
        self.enabled = True

    def do(self):
        if not self.enabled:
            return
        SimpleAction.do(self)
        mw = self.__main_win
        mw.zoom_level['auto'] = False
        mw.update_page_sizes()


class ActionRefreshBoxes(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Refresh current page boxes")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_boxes()


class ActionToggleAllBoxes(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Toggle all boxes visibility")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_boxes()


class ActionToggleLabel(object):
    def __init__(self, main_window):
        self.__main_win = main_window

    def toggle_cb(self, renderer, objpath):
        label = self.__main_win.lists['labels']['model'][objpath][2]
        if label not in self.__main_win.doc.labels:
            logger.info("Action: Adding label '%s' on document '%s'"
                        % (label.name, str(self.__main_win.doc)))
            self.__main_win.docsearch.add_label(self.__main_win.doc, label,
                                                update_index=False)
        else:
            logger.info("Action: Removing label '%s' on document '%s'"
                        % (label.name, self.__main_win.doc))
            self.__main_win.docsearch.remove_label(self.__main_win.doc, label,
                                                   update_index=False)
        self.__main_win.refresh_label_list()
        self.__main_win.refresh_docs({self.__main_win.doc},
                                     redo_thumbnails=False)
        job = self.__main_win.job_factories['index_updater'].make(
            self.__main_win.docsearch, upd_docs={self.__main_win.doc},
            optimize=False)
        self.__main_win.schedulers['main'].schedule(job)

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
            logger.info("Adding label %s to doc %s"
                        % (labeleditor.label.name, self.__main_win.doc))
            job = self.__main_win.job_factories['label_creator'].make(
                self.__main_win.docsearch, labeleditor.label,
                self.__main_win.doc)
            self.__main_win.schedulers['main'].schedule(job)


class ActionEditLabel(SimpleAction):
    """
    Edit the selected label.
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Editing label")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        # Open the russian dolls to retrieve the selected label.
        label_list = self.__main_win.lists['labels']['gui']
        selected_row = label_list.get_selected_row()
        if selected_row is None:
            logger.warning("No label selected")
            return True
        label_box = selected_row.get_children()[0]
        label_name = label_box.get_children()[1].get_text()
        label_color = label_box.get_children()[2].get_rgba().to_string()
        label = Label(label_name, label_color)

        new_label = copy(label)
        editor = LabelEditor(new_label)
        if not editor.edit(self.__main_win.window):
            logger.warning("Label edition cancelled")
            return
        logger.info("Label edited. Applying changes")
        job = self.__main_win.job_factories['label_updater'].make(
            self.__main_win.docsearch, label, new_label)
        self.__main_win.schedulers['main'].schedule(job)


class ActionDeleteLabel(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Deleting label")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        if not ask_confirmation(self.__main_win.window):
            return

        label_list = self.__main_win.lists['labels']['gui']
        selection_path = label_list.get_selection().get_selected()
        if selection_path[1] is None:
            logger.warning("No label selected")
            return True
        label = selection_path[0].get_value(selection_path[1], 2)

        job = self.__main_win.job_factories['label_deleter'].make(
            self.__main_win.docsearch, label)
        self.__main_win.schedulers['main'].schedule(job)


class ActionOpenDocDir(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open doc dir")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        os.system('xdg-open "%s" &' % (self.__main_win.doc.path))


class ActionPrintDoc(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open print dialog")
        self.__main_win = main_window

    class PrintPageCb(object):
        def __init__(self, doc, keep_refs):
            self.doc = doc
            self.keep_refs = keep_refs

        def print_page_cb(self, print_op, print_context, page_nb):
            self.doc.print_page_cb(print_op, print_context, page_nb,
                                   self.keep_refs)

    def do(self):
        SimpleAction.do(self)

        keep_refs = {}
        cb = self.PrintPageCb(self.__main_win.doc, keep_refs)

        print_settings = Gtk.PrintSettings()
        print_op = Gtk.PrintOperation()
        print_op.set_print_settings(print_settings)
        print_op.set_n_pages(self.__main_win.doc.nb_pages)
        print_op.set_current_page(self.__main_win.page.page_nb)
        print_op.set_use_full_page(False)
        print_op.set_job_name(str(self.__main_win.doc))
        print_op.set_export_filename(str(self.__main_win.doc) + ".pdf")
        print_op.set_allow_async(False)
        print_op.connect("draw-page", cb.print_page_cb)
        print_op.set_embed_page_setup(True)
        print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG,
                     self.__main_win.window)
        del keep_refs


class ActionOpenSettings(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Open settings dialog")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        sw = SettingsWindow(self.__main_win.schedulers['main'],
                            self.__main_win.window, self.__config)
        sw.connect("need-reindex", self.__reindex_cb)

    def __reindex_cb(self, settings_window):
        self.__main_win.actions['reindex'][1].do()


class ActionSingleScan(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Scan a single page")
        self.__main_win = main_window
        self.__config = config

    def __on_scan_ocr_canceled(self, scan_workflow):
        docid = self.__main_win.remove_scan_workflow(scan_workflow)
        if self.__main_win.doc.docid == docid:
            self.__main_win.show_page(self.__main_win.doc.pages[-1],
                                      force_refresh=True)

    def __on_scan_error(self, scan_workflow, exc):
        # TODO
        docid = self.__main_win.remove_scan_workflow(scan_workflow)
        if self.__main_win.doc.docid == docid:
            self.__main_win.show_page(self.__main_win.doc.pages[-1],
                                      force_refresh=True)

    def __on_ocr_done(self, scan_workflow, img, line_boxes):
        docid = self.__main_win.remove_scan_workflow(scan_workflow)
        self.__main_win.add_page(docid, img, line_boxes)

    def do(self):
        SimpleAction.do(self)
        if not check_scanner(self.__main_win, self.__config):
            return

        try:
            (dev, resolution) = get_scanner(self.__config)
            scan_session = dev.scan(multiple=False)
        except Exception, exc:
            logger.warning("Exception while configuring scanner: %s: %s."
                           " Assuming scanner is not connected",
                           type(exc), exc)
            popup_no_scanner_found(self.__main_win.window)
            return

        scan_workflow = self.__main_win.make_scan_workflow()
        scan_workflow.connect('scan-canceled', lambda scan_workflow:
                              GLib.idle_add(self.__on_scan_ocr_canceled,
                                            scan_workflow))
        scan_workflow.connect('scan-error', lambda scan_scan, exc:
                              GLib.idle_add(self.__on_scan_error,
                                            scan_workflow,
                                            exc))
        scan_workflow.connect('ocr-canceled', lambda scan_workflow:
                              GLib.idle_add(self.__on_scan_ocr_canceled,
                                            scan_workflow))
        scan_workflow.connect('process-done', lambda scan_workflow, img, boxes:
                              GLib.idle_add(self.__on_ocr_done, scan_workflow,
                                            img, boxes))

        drawer = self.__main_win.make_scan_workflow_drawer(
            scan_workflow, single_angle=False)
        self.__main_win.add_scan_workflow(self.__main_win.doc, drawer)
        scan_workflow.scan_and_ocr(resolution, scan_session)


class ActionMultiScan(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Scan multiples pages")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        if not check_scanner(self.__main_win, self.__config):
            return
        ms = MultiscanDialog(self.__main_win, self.__config)
        ms.connect("need-show-page",
                   lambda ms_dialog, page:
                   GLib.idle_add(self.__show_page, page))

    def __show_page(self, page):
        self.__main_win.refresh_doc_list()
        self.__main_win.show_page(page)


class ActionImport(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Import file(s)")
        self.__main_win = main_window
        self.__config = config

    def __select_file(self):
        widget_tree = load_uifile(
            os.path.join("import", "importfileselector.glade"))
        dialog = widget_tree.get_object("filechooserdialog")
        dialog.set_local_only(False)
        dialog.set_select_multiple(False)

        response = dialog.run()
        if response != 0:
            logger.info("Import: Canceled by user")
            dialog.destroy()
            return None
        file_uri = dialog.get_uri()
        dialog.destroy()
        logger.info("Import: %s" % file_uri)
        return file_uri

    def __select_importer(self, importers):
        widget_tree = load_uifile(
            os.path.join("import", "importaction.glade"))
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
        return importer_list[active_idx][1]

    def __no_importer(self, file_uri):
        msg = (_("Don't know how to import '%s'. Sorry.") %
               (os.path.basename(file_uri)))
        flags = (Gtk.DialogFlags.MODAL
                 | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.__main_win.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.run()
        dialog.destroy()

    def __no_doc_imported(self):
        msg = _("No new document to import found")
        flags = (Gtk.DialogFlags.MODAL
                 | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.__main_win.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.run()
        dialog.destroy()

    def do(self):
        SimpleAction.do(self)

        file_uri = self.__select_file()
        if file_uri is None:
            return

        importers = docimport.get_possible_importers(
            file_uri, self.__main_win.doc)
        if len(importers) <= 0:
            self.__no_importer(file_uri)
            return
        elif len(importers) > 1:
            importer = self.__select_importers(importers)
        else:
            importer = importers[0]

        Gtk.RecentManager().add_item(file_uri)

        job_importer = self.__main_win.job_factories['importer']
        job_importer = job_importer.make(importer, file_uri)
        job_importer.connect('no-doc-imported',
                             lambda _: self.__no_doc_imported())
        self.__main_win.schedulers['main'].schedule(job_importer)


class ActionDeleteDoc(SimpleAction):
    def __init__(self, main_window, doc=None):
        SimpleAction.__init__(self, "Delete document")
        self.__main_win = main_window
        self.__doc = doc

    def do(self):
        """
        Ask for confirmation and then delete the document being viewed.
        """
        if not ask_confirmation(self.__main_win.window):
            return
        SimpleAction.do(self)
        if self.__doc is None:
            doc = self.__main_win.doc
        else:
            doc = self.__doc
        docid = doc.docid

        self.__main_win.actions['new_doc'][1].do()

        logger.info("Deleting ...")
        doc.destroy()
        index_upd = self.__main_win.docsearch.get_index_updater(
            optimize=False)
        index_upd.del_doc(docid)
        index_upd.commit()
        logger.info("Deleted")

        self.__main_win.refresh_doc_list()


class ActionDeletePage(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Delete page")
        self.__main_win = main_window

    def do(self, page=None):
        """
        Ask for confirmation and then delete the page being viewed.
        """
        if not ask_confirmation(self.__main_win.window):
            return

        if page is None:
            page = self.__main_win.page
        doc = page.doc

        SimpleAction.do(self)
        logger.info("Deleting ...")
        page.destroy()
        logger.info("Deleted")
        doc.drop_cache()
        self.__main_win.page = None
        set_widget_state(self.__main_win.need_page_widgets, False)
        if len(doc.pages) > 0:
            self.__main_win.refresh_docs({doc})
        else:
            self.__main_win.refresh_doc_list()
        self.__main_win.show_doc(self.__main_win.doc, force_refresh=True)

        if doc.nb_pages <= 0:
            job = self.__main_win.job_factories['index_updater'].make(
                self.__main_win.docsearch, del_docs={doc.docid},
                optimize=False)
        else:
            job = self.__main_win.job_factories['index_updater'].make(
                self.__main_win.docsearch, upd_docs={doc}, optimize=False)
        self.__main_win.schedulers['main'].schedule(job)


class ActionRedoOCR(SimpleAction):
    def __init__(self, name, main_window, ask_confirmation=True):
        SimpleAction.__init__(self, name)
        self._main_win = main_window
        self.ask_confirmation = ask_confirmation

    def _do_next_page(self, page_iterator, docs_done=None):
        try:
            page = next(page_iterator)
        except StopIteration:
            logger.info("OCR has been redone on all the target pages")
            raise

        if page.doc != self._main_win.doc:
            self._main_win.show_doc(page.doc)

        logger.info("Redoing OCR on %s" % str(page))
        scan_workflow = self._main_win.make_scan_workflow()
        drawer = self._main_win.make_scan_workflow_drawer(
            scan_workflow, single_angle=True, page=page)
        self._main_win.add_scan_workflow(page.doc, drawer,
                                         page_nb=page.page_nb)
        scan_workflow.connect('process-done',
                              lambda scan_workflow, img, boxes:
                              GLib.idle_add(self._on_page_ocr_done,
                                            scan_workflow,
                                            img, boxes, page, page_iterator,
                                            docs_done))
        scan_workflow.ocr(page.img, angles=1)

    def _on_page_ocr_done(self, scan_workflow, img, boxes, page, page_iterator,
                          docs_done=None):
        if docs_done is None:
            docs_done = set()
        page.boxes = boxes

        docid = self._main_win.remove_scan_workflow(scan_workflow)

        doc = self._main_win.docsearch.get_doc_from_docid(docid)
        docs_done.add(doc)

        try:
            self._do_next_page(page_iterator)
        except StopIteration:
            if self._main_win.doc in docs_done:
                self._main_win.show_doc(self._main_win.doc, force_refresh=True)
            job = self._main_win.job_factories['index_updater'].make(
                self._main_win.docsearch, upd_docs=docs_done, optimize=False)
            self._main_win.schedulers['main'].schedule(job)

    def do(self, pages_iterator):
        if (self.ask_confirmation
                and not ask_confirmation(self._main_win.window)):
            return
        SimpleAction.do(self)
        self._do_next_page(pages_iterator)


class AllPagesIterator(object):
    def __init__(self, docsearch):
        self.__doc_iter = iter(docsearch.docs)
        doc = self.__doc_iter.next()
        self.__page_iter = iter(doc.pages)

    def __iter__(self):
        return self

    def next(self):
        while True:
            try:
                return next(self.__page_iter)
            except StopIteration:
                doc = next(self.__doc_iter)
                self.__page_iter = iter(doc.pages)


class ActionRedoAllOCR(ActionRedoOCR):
    def __init__(self, main_window):
        ActionRedoOCR.__init__(self, "Redoing all ocr", main_window)

    def do(self):
        docsearch = self._main_win.docsearch
        all_page_iter = AllPagesIterator(docsearch)
        ActionRedoOCR.do(self, all_page_iter)


class ActionRedoDocOCR(ActionRedoOCR):
    def __init__(self, main_window):
        ActionRedoOCR.__init__(self, "Redoing doc ocr", main_window)

    def do(self):
        doc = self._main_win.doc
        ActionRedoOCR.do(self, iter(doc.pages))


class ActionRedoPageOCR(ActionRedoOCR):
    def __init__(self, main_window):
        ActionRedoOCR.__init__(self, "Redoing page ocr",
                               main_window, ask_confirmation=False)

    def do(self, page=None):
        if page is None:
            page = self._main_win.page
        ActionRedoOCR.do(self, iter([page]))




class BasicActionOpenExportDialog(SimpleAction):
    def __init__(self, main_window, action_txt):
        SimpleAction.__init__(self, action_txt)
        self.main_win = main_window

    def open_dialog(self, to_export):
        SimpleAction.do(self)
        self.main_win.export['estimated_size'].set_text("")
        self.main_win.export['fileFormat']['model'].clear()
        nb_export_formats = 0
        formats = to_export.get_export_formats()
        logger.info("[Export]: Supported formats: %s" % formats)
        for out_format in to_export.get_export_formats():
            self.main_win.export['fileFormat']['model'].append([out_format])
            nb_export_formats += 1
        self.main_win.export['buttons']['select_path'].set_sensitive(
            nb_export_formats >= 1)
        self.main_win.export['fileFormat']['widget'].set_active(0)
        self.main_win.export['dialog'].set_visible(True)
        self.main_win.export['buttons']['ok'].set_sensitive(False)
        self.main_win.export['export_path'].set_text("")
        for button in self.main_win.actions['open_view_settings'][0]:
            button.set_sensitive(False)
        self.main_win.drop_boxes()

        self.main_win.export['pageFormat']['model'].clear()
        idx = 0
        default_idx = -1
        for paper_size in Gtk.PaperSize.get_paper_sizes(True):
            store_data = (
                paper_size.get_display_name(),
                paper_size.get_width(Gtk.Unit.POINTS),
                paper_size.get_height(Gtk.Unit.POINTS)
            )
            self.main_win.export['pageFormat']['model'].append(store_data)
            if paper_size.get_name() == paper_size.get_default():
                default_idx = idx
            idx += 1
        if default_idx >= 0:
            widget = self.main_win.export['pageFormat']['widget']
            widget.set_active(default_idx)


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
        file_format_widget = self.__main_win.export['fileFormat']['widget']
        format_idx = file_format_widget.get_active()
        if format_idx < 0:
            return
        file_format_model = self.__main_win.export['fileFormat']['model']
        imgformat = file_format_model[format_idx][0]

        target = self.__main_win.export['to_export']
        exporter = target.build_exporter(imgformat)
        self.__main_win.export['exporter'] = exporter

        logger.info("[Export] Format: %s" % (exporter))
        logger.info("[Export] Can change quality ? %s"
                    % exporter.can_change_quality)
        logger.info("[Export] Can_select_format ? %s"
                    % exporter.can_select_format)

        widgets = [
            (exporter.can_change_quality,
             [
                 self.__main_win.export['quality']['widget'],
                 self.__main_win.export['quality']['label'],
             ]),
            (exporter.can_select_format,
             [
                 self.__main_win.export['pageFormat']['widget'],
                 self.__main_win.export['pageFormat']['label'],
             ]),
        ]
        for (sensitive, widgets) in widgets:
            set_widget_state(widgets, sensitive)

        if exporter.can_change_quality or exporter.can_select_format:
            self.__main_win.actions['change_export_property'][1].do()
        else:
            size_txt = sizeof_fmt(exporter.estimate_size())
            self.__main_win.export['estimated_size'].set_text(size_txt)


class ActionChangeExportProperty(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Export property changed")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        assert(self.__main_win.export['exporter'] is not None)
        if self.__main_win.export['exporter'].can_select_format:
            page_format_widget = self.__main_win.export['pageFormat']['widget']
            format_idx = page_format_widget.get_active()
            if (format_idx < 0):
                return
            page_format_model = self.__main_win.export['pageFormat']['model']
            (name, x, y) = page_format_model[format_idx]
            self.__main_win.export['exporter'].set_page_format((x, y))
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
                                        transient_for=self.__main_win.window,
                                        action=Gtk.FileChooserAction.SAVE)
        chooser.add_buttons(Gtk.STOCK_CANCEL,
                             Gtk.ResponseType.CANCEL,
                             Gtk.STOCK_SAVE,
                             Gtk.ResponseType.OK)
        file_filter = Gtk.FileFilter()
        file_filter.set_name(str(self.__main_win.export['exporter']))
        mime = self.__main_win.export['exporter'].get_mime_type()
        file_filter.add_mime_type(mime)
        chooser.add_filter(file_filter)

        response = chooser.run()
        filepath = chooser.get_filename()
        chooser.destroy()
        if response != Gtk.ResponseType.OK:
            logger.warning("File path for export canceled")
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


class BasicActionEndExport(SimpleAction):
    def __init__(self, main_win, name):
        SimpleAction.__init__(self, name)
        self.main_win = main_win

    def do(self):
        SimpleAction.do(self)
        for button in self.main_win.actions['open_view_settings'][0]:
            button.set_sensitive(False)
        self.main_win.export['dialog'].set_visible(False)
        self.main_win.export['exporter'] = None
        # force refresh of the current page
        self.main_win.show_page(self.main_win.page, force_refresh=True)


class ActionExport(BasicActionEndExport):
    def __init__(self, main_window):
        BasicActionEndExport.__init__(self, main_window, "Export")
        self.main_win = main_window

    def do(self):
        filepath = self.main_win.export['export_path'].get_text()
        self.main_win.export['exporter'].save(filepath)
        BasicActionEndExport.do(self)


class ActionCancelExport(BasicActionEndExport):
    def __init__(self, main_window):
        BasicActionEndExport.__init__(self, main_window, "Cancel export")

    def do(self):
        BasicActionEndExport.do(self)


class ActionOptimizeIndex(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Optimize index")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        job = self.__main_win.job_factories['index_updater'].make(
            self.__main_win.docsearch, optimize=True)
        self.__main_win.schedulers['main'].schedule(job)


class ActionAbout(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Opening about dialog")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
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
        Gtk.main_quit()

    def on_window_close_cb(self, window):
        self.do()


class ActionRefreshIndex(SimpleAction):
    def __init__(self, main_window, config, force=False):
        SimpleAction.__init__(self, "Refresh index")
        self.__main_win = main_window
        self.__config = config
        self.__force = force
        self.__connect_handler_id = None

    def do(self):
        SimpleAction.do(self)
        self.__main_win.schedulers['main'].cancel_all(
            self.__main_win.job_factories['index_reloader'])
        self.__main_win.schedulers['main'].cancel_all(
            self.__main_win.job_factories['doc_examiner'])
        self.__main_win.schedulers['main'].cancel_all(
            self.__main_win.job_factories['index_updater'])
        docsearch = self.__main_win.docsearch
        self.__main_win.docsearch = DummyDocSearch()
        if self.__force:
            docsearch.destroy_index()

        job = self.__main_win.job_factories['index_reloader'].make()
        job.connect('index-loading-end', self.__on_index_reload_end)
        self.__main_win.schedulers['main'].schedule(job)

    def __on_index_reload_end(self, job, docsearch):
        if docsearch is None:
            return
        job = self.__main_win.job_factories['doc_examiner'].make(docsearch)
        job.connect('doc-examination-end', lambda job: GLib.idle_add(
            self.__on_doc_exam_end, job))
        self.__main_win.schedulers['main'].schedule(job)

    def __on_doc_exam_end(self, examiner):
        logger.info("Document examen finished. Updating index ...")
        logger.info("New document: %d" % len(examiner.new_docs))
        logger.info("Updated document: %d" % len(examiner.docs_changed))
        logger.info("Deleted document: %d" % len(examiner.docs_missing))

        if (len(examiner.new_docs) == 0
                and len(examiner.docs_changed) == 0
                and len(examiner.docs_missing) == 0):
            logger.info("No changes")
            return

        job = self.__main_win.job_factories['index_updater'].make(
            docsearch=examiner.docsearch,
            new_docs=examiner.new_docs,
            upd_docs=examiner.docs_changed,
            del_docs=examiner.docs_missing,
            reload_list=True,
            optimize=False
        )
        self.__main_win.schedulers['main'].schedule(job)


class ActionSwitchToDocList(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Switch back to doc list")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.doc_properties_panel.apply_properties()
        self.__main_win.switch_leftpane("doc_list")


class ActionSetDocDate(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Set document date")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        calendar = self.__main_win.doc_properties_panel.widgets['calendar']
        popover = self.__main_win.popovers['calendar']
        date = calendar.get_date()
        date = datetime.datetime(year=date[0], month=date[1] + 1, day=date[2])
        date_txt = BasicDoc.get_name(date)

        entry = self.__main_win.doc_properties_panel.widgets['name']
        entry.set_text(date_txt)

        if self.__main_win.doc_properties_panel.doc.date != date:
            self.__main_win.doc_properties_panel.new_doc_date = date
        else:
            self.__main_win.doc_properties_panel.new_doc_date = None

        popover.set_visible(False)


def connect_actions(actions):
    for action in actions:
        for button in actions[action][0]:
            if button is None:
                logger.error("MISSING BUTTON: %s" % (action))
        try:
            actions[action][1].connect(actions[action][0])
        except:
            logger.error("Failed to connect action '%s'" % action)
            raise


class DocPropertiesPanel(object):
    def __init__(self, main_window, widget_tree):
        self.__main_win = main_window
        self.widgets = {
            'ok': widget_tree.get_object("toolbuttonValidateDocProperties"),
            'name': widget_tree.get_object("docname_entry"),
            'labels': widget_tree.get_object("listboxLabels"),
            'row_add_label': widget_tree.get_object("rowAddLabel"),
            'button_add_label': widget_tree.get_object("buttonAddLabel"),
            'extra_keywords': widget_tree.get_object("extrakeywords_textview"),
            'extra_keywords_default_buffer': \
                widget_tree.get_object("extrakeywords_default_textbuffer"),
            'calendar': widget_tree.get_object("calendar_calendar"),
        }
        self.doc = self.__main_win.doc
        self.new_doc_date = None
        self.actions = {
            'apply_doc_edit': (
                [
                    self.widgets['ok']
                ],
                ActionSwitchToDocList(self.__main_win),
            ),
            'set_day': (
                [
                    self.widgets['calendar']
                ],
                ActionSetDocDate(self.__main_win),
            ),
        }
        connect_actions(self.actions)

        self.widgets['name'].connect(
            "icon-release", lambda entry, icon, event:
            GLib.idle_add(self._open_calendar))

        labels = sorted(main_window.docsearch.label_list)
        self.labels = {label: (None, None) for label in labels}

        default_buf = self.widgets['extra_keywords_default_buffer']
        self.default_extra_text = self.get_text_from_buffer(default_buf)
        self.widgets['extra_keywords'].connect("focus-in-event",
                                                self.on_keywords_focus_in)
        self.widgets['extra_keywords'].connect("focus-out-event",
                                                self.on_keywords_focus_out)

    def get_text_from_buffer(self, text_buffer):
        start = text_buffer.get_iter_at_offset(0)
        end = text_buffer.get_iter_at_offset(-1)
        return unicode(text_buffer.get_text(start, end, False),
                       encoding='utf-8')

    def set_doc(self, doc):
        self.doc = doc
        self.reload_properties()

    def reload_properties(self):
        self.widgets['name'].set_text(self.doc.name)
        self.refresh_label_list()
        self.refresh_keywords_textview()

    def _open_calendar(self):
        self.__main_win.popovers['calendar'].set_relative_to(
            self.widgets['name'])
        if self.new_doc_date is not None:
            self.widgets['calendar'].select_month(
                self.new_doc_date.month - 1,
                self.new_doc_date.year
            )
            self.widgets['calendar'].select_day(self.new_doc_date.day)
        else:
            try:
                date = self.doc.date
                self.widgets['calendar'].select_month(date.month - 1, date.year)
                self.widgets['calendar'].select_day(date.day)
            except Exception as exc:
                logger.warning("Failed to parse document date: %s --> %s"
                                % (str(self.doc.docid), str(exc)))
        self.__main_win.popovers['calendar'].set_visible(True)

    def apply_properties(self):
        has_changed = False

        # Labels
        logger.info("Checking for new labels")
        doc_labels = sorted(self.doc.labels)
        new_labels = []
        for (label, (check_button, edit_button)) in self.labels.iteritems():
            if check_button.get_active():
                new_labels.append(label)
        new_labels.sort()
        if doc_labels != new_labels:
            logger.info("Apply new labels")
            self.doc.labels = new_labels
            has_changed = True

        # Keywords
        logger.info("Checking for new keywords")
        # text currently set
        current_extra_text = self.doc.extra_text
        # text actually typed in
        buf = self.widgets['extra_keywords'].get_buffer()
        new_extra_text = self.get_text_from_buffer(buf)
        if (new_extra_text != current_extra_text) and (
                new_extra_text != self.default_extra_text):
            logger.info("Apply new keywords")
            self.doc.extra_text = new_extra_text
            has_changed = True

        # Date
        if self.new_doc_date is None:
            if has_changed:
                self.__main_win.upd_index(self.doc)
        else:
            old_docid = self.doc.docid
            self.doc.date = self.new_doc_date
            self.new_doc_date = None
            # this case is more tricky --> del + new
            job = self.__main_win.job_factories['index_updater'].make(
                 self.__main_win.docsearch,
                 new_docs={self.doc},
                 del_docs={old_docid},
                 optimize=False,
                 reload_list=True)
            self.__main_win.schedulers['main'].schedule(job)

        self.__main_win.refresh_header_bar()


    def _clear_label_list(self):
        self.widgets['labels'].freeze_child_notify()
        try:
            while True:
                row = self.widgets['labels'].get_row_at_index(0)
                if row is None:
                    break
                self.widgets['labels'].remove(row)
        finally:
            self.labels = {}
            self.widgets['labels'].thaw_child_notify()

    def _readd_label_widgets(self, labels):
        label_widgets = {}
        self.widgets['labels'].freeze_child_notify()
        try:
            # Add a row for each label
            for label in labels:
                label_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 10)

                # Custom check_button with unvisible checkbox
                empty_image= Gtk.Image()
                check_button = Gtk.ToggleButton()
                check_button.set_image(empty_image)
                check_button.set_always_show_image(True)
                check_button.set_relief(Gtk.ReliefStyle.NONE)
                check_style = check_button.get_style_context()
                check_style.remove_class("button")
                check_button.connect("clicked", self.on_check_button_clicked)
                label_box.add(check_button)

                label_widget = Gtk.Label.new(label.name)
                label_widget.set_halign(Gtk.Align.START)
                label_box.add(label_widget)
                label_box.child_set_property(label_widget, 'expand', True)

                # Custom color_button wich opens custom dialog
                edit_button = LabelColorButton()
                edit_button.set_rgba(label.color)
                edit_button.set_relief(Gtk.ReliefStyle.NONE)
                edit_button.connect("clicked", self.on_label_button_clicked)
                ActionEditLabel(self.__main_win).connect([edit_button])
                label_box.add(edit_button)

                rowbox = Gtk.ListBoxRow()
                rowbox.add(label_box)
                rowbox.set_property('height_request', 30)
                rowbox.show_all()
                self.widgets['labels'].add(rowbox)

                label_widgets[label] = (check_button, edit_button)

            # The last row allows to add new labels
            self.widgets['labels'].add(self.widgets['row_add_label'])
        finally:
            self.labels = label_widgets
            self.widgets['labels'].connect("row-activated", self.on_row_activated)
            self.widgets['labels'].thaw_child_notify()

    def on_check_button_clicked(self, check_button):
        """
        Toggle the image displayed into the check_button
        """
        if check_button.get_active():
            checkmark = Gtk.Image.new_from_icon_name("object-select-symbolic",
                                                     Gtk.IconSize.MENU)
            check_button.set_image(checkmark)
        else:
            empty_image= Gtk.Image()
            check_button.set_image(empty_image)

    def on_label_button_clicked(self, button):
        """
        Find the row the button belongs to, and select it.
        """
        label_box = button.get_parent()
        row = label_box.get_parent()
        label_list = self.__main_win.lists['labels']['gui']
        label_list.select_row(row)

    def on_row_activated(self, rowbox, row):
        """
        When no specific part of a row is clicked on, do as if user had clicked
        on it's check_button. This requires less precision for the user.
        """
        row = rowbox.get_selected_row()
        label_box = row.get_children()[0]
        check_button = label_box.get_children()[0]
        if check_button.get_active():
            check_button.set_active(False)
        else:
            check_button.set_active(True)

    def refresh_label_list(self):
        all_labels = sorted(self.__main_win.docsearch.label_list)
        current_labels = sorted(self.labels.keys())
        if all_labels != current_labels:
            self._clear_label_list()
            self._readd_label_widgets(all_labels)
        for label in self.labels:
            if self.doc:
                active = label in self.doc.labels
            else:
                active = False
            self.labels[label][0].set_active(active)

    def on_keywords_focus_in(self, textarea, event):
        extra_style = self.widgets['extra_keywords'].get_style_context()
        extra_style.remove_class("extra-hint")
        text_buffer = self.widgets['extra_keywords'].get_buffer()
        text = self.get_text_from_buffer(text_buffer)
        if (text == self.default_extra_text):
            # Clear the hint
            text_buffer.set_text('')

    def on_keywords_focus_out(self, textarea, event):
        text_buffer = self.widgets['extra_keywords'].get_buffer()
        text = self.get_text_from_buffer(text_buffer)
        if (len(text) == 0) or (text == ''):
            # Add the hint back
            text_buffer.set_text(self.default_extra_text)
            extra_style = self.widgets['extra_keywords'].get_style_context()
            extra_style.add_class("extra-hint")

    def refresh_keywords_textview(self):
        """
        Display paper keywords or a hint.
        """
        extra_style = self.widgets['extra_keywords'].get_style_context()
        extra_style.remove_class("extra-hint")
        text_buffer = self.widgets['extra_keywords'].get_buffer()
        if len(self.doc.extra_text) > 0:
            text_buffer.set_text(self.doc.extra_text)
        else:
            text_buffer.set_text(self.default_extra_text)
            extra_style.add_class("extra-hint")

        self.widgets['extra_keywords'].set_buffer(text_buffer)


class MainWindow(object):
    SMALL_THUMBNAIL_WIDTH = 64
    SMALL_THUMBNAIL_HEIGHT = 80

    def __init__(self, config):
        self.app = self.__init_app()
        gactions = self.__init_gactions(self.app)

        self.schedulers = self.__init_schedulers()
        self.default_thumbnail = self.__init_default_thumbnail()
        self.default_small_thumbnail = self.__init_default_thumbnail(
            self.SMALL_THUMBNAIL_WIDTH, self.SMALL_THUMBNAIL_HEIGHT)

        # used by the set_mouse_cursor() function to keep track of how many
        # threads / jobs requested a busy mouse cursor
        self.__busy_mouse_counter = 0

        self.__advanced_app_menu = self.__init_app_menu(self.app)

        load_cssfile("application.css")
        widget_tree = load_uifile(
            os.path.join("mainwindow", "mainwindow.glade"))

        self.window = self.__init_window(widget_tree, config)

        self.__config = config
        self.__scan_start = 0.0
        self.__scan_progress_job = None

        self.docsearch = DummyDocSearch()
        self.doc = ImgDoc(self.__config['workdir'].value)
        self.new_doc = self.doc

        # All the pages are displayed on the canvas,
        # however, only one is the "active one"
        self.page = DummyPage(self.doc)
        self.page_drawers = []
        self.layout = "grid"
        self.scan_drawers = {}  # docid --> {page_nb: extra drawer}

        search_completion = Gtk.EntryCompletion()

        open_doc_action = ActionOpenSelectedDocument(self, config)

        self.zoom_level = {
            'gui': widget_tree.get_object("scaleZoom"),
            'model': widget_tree.get_object("adjustmentZoom"),
            'auto': True,  # recomputed if the window size change
        }

        self.lists = {
            'suggestions': {
                'gui': widget_tree.get_object("entrySearch"),
                'completion': search_completion,
                'model': widget_tree.get_object("liststoreSuggestion")
            },
            'labels': {
              'gui': widget_tree.get_object("listboxLabels")
            },
            'doclist': {
                'gui': widget_tree.get_object("listboxDocList"),
                'model': {
                    'has_new': False,
                    'by_row': {},  # Gtk.ListBoxRow: docid
                    'by_id': {},  # docid: Gtk.ListBoxRow
                },
            },
        }

        search_completion.set_model(self.lists['suggestions']['model'])
        search_completion.set_text_column(0)
        search_completion.set_match_func(lambda a, b, c, d: True, None)
        self.lists['suggestions']['gui'].set_completion(search_completion)

        self.search_field = widget_tree.get_object("entrySearch")
        self.search_field.connect("icon-press",
                                  self._on_search_field_icon_activated)

        self.doc_browsing = {
            'search': self.search_field,
        }

        img_scrollbars = widget_tree.get_object("scrolledwindowPageImg")
        img_widget = Canvas(img_scrollbars)
        img_widget.set_visible(True)
        img_scrollbars.add(img_widget)

        img_widget.connect(None,
            'window-moved',
            lambda x: GLib.idle_add(self.__on_img_window_moved))

        self.progressbar = ProgressBarDrawer()
        self.progressbar.visible = False
        img_widget.add_drawer(self.progressbar)

        img_widget.connect(None,
            'window-moved',
            lambda x: GLib.idle_add(self.__on_img_window_moved))

        self.img = {
            "canvas": img_widget,
            "scrollbar": img_scrollbars,
            "viewport": {
                "widget": img_widget,
                "size": (0, 0),
            },
            "eventbox": widget_tree.get_object("eventboxImg"),
            "pixbuf": None,
            "factor": 1.0,
            "original_width": 1,
            "boxes": {
                'all': [],
                'visible': [],
                'highlighted': [],
                'selected': [],
            }
        }

        self.popovers = {
            'view_settings': widget_tree.get_object("view_settings_popover"),
            'calendar': widget_tree.get_object("calendar_popover"),
        }

        self.popup_menus = {}

        self.doc_properties_panel = DocPropertiesPanel(self, widget_tree)

        self.headerbars = {
            'left': widget_tree.get_object("headerbar_left"),
            'right': widget_tree.get_object("headerbar_right"),
        }

        self.left_revealers = {
            'doc_list': [
                widget_tree.get_object("box_left_doclist_revealer"),
                widget_tree.get_object("box_headerbar_left_doclist_revealer"),
            ],
            'doc_properties': [
                widget_tree.get_object("box_left_docproperties_revealer"),
                widget_tree.get_object(
                    "box_headerbar_left_docproperties_revealer"),
            ],
        }

        self.page_nb = {
            'current': widget_tree.get_object("entryPageNb"),
            'total': widget_tree.get_object("labelTotalPages"),
        }

        self.export = {
            'dialog': widget_tree.get_object("infobarExport"),
            'fileFormat': {
                'widget': widget_tree.get_object("comboboxExportFormat"),
                'model': widget_tree.get_object("liststoreExportFormat"),
            },
            'pageFormat': {
                'label': widget_tree.get_object("labelPageFormat"),
                'widget': widget_tree.get_object("comboboxPageFormat"),
                'model': widget_tree.get_object("liststorePageFormat"),
            },
            'quality': {
                'label': widget_tree.get_object("labelExportQuality"),
                'widget': widget_tree.get_object("scaleQuality"),
                'model': widget_tree.get_object("adjustmentQuality"),
            },
            'estimated_size':
            widget_tree.get_object("labelEstimatedExportSize"),
            'export_path': widget_tree.get_object("entryExportPath"),
            'buttons': {
                'select_path':
                widget_tree.get_object("buttonSelectExportPath"),
                'ok': widget_tree.get_object("buttonExport"),
                'cancel': widget_tree.get_object("buttonCancelExport"),
            },
            'to_export': None,  # usually self.page or self.doc
            'exporter': None,
        }

        self.layouts = {
            'settings_button': widget_tree.get_object("viewSettingsButton"),
            'grid': {
                'button': widget_tree.get_object("show_grid_button"),
            },
            'paged': {
                'button': widget_tree.get_object("show_paged_button"),
            },
        }

        self.job_factories = {
            'doc_examiner': JobFactoryDocExaminer(self, config),
            'doc_thumbnailer': JobFactoryDocThumbnailer(self),
            'export_previewer': JobFactoryExportPreviewer(self),
            'importer': JobFactoryImporter(self, config),
            'index_reloader': JobFactoryIndexLoader(self, config),
            'index_updater': JobFactoryIndexUpdater(self, config),
            'label_creator': JobFactoryLabelCreator(self),
            'label_updater': JobFactoryLabelUpdater(self),
            'label_predictor_on_open_doc': JobFactoryLabelPredictorOnOpenDoc(
                self
            ),
            'label_predictor_on_new_doc': JobFactoryLabelPredictorOnNewDoc(
                self
            ),
            'label_deleter': JobFactoryLabelDeleter(self),
            'page_img_renderer': JobFactoryPageImgRenderer(),
            'page_img_loader': JobFactoryPageImgLoader(),
            'page_boxes_loader': JobFactoryPageBoxesLoader(),
            'searcher': JobFactoryDocSearcher(self, config),
        }

        self.actions = {
            'new_doc': (
                [
                    widget_tree.get_object("toolbuttonNewDoc"),
                ],
                ActionNewDocument(self, config),
            ),
            'open_doc': (
                [
                    widget_tree.get_object("listboxDocList"),
                ],
                open_doc_action,
            ),
            'open_view_settings': (
                [
                    self.layouts['settings_button'],
                ],
                ActionOpenViewSettings(self),
            ),
            'show_as_grid': (
                [
                    self.layouts['grid']['button'],
                ],
                ActionShowDocumentAsGrid(self)
            ),
            'show_as_paged': (
                [
                    self.layouts['paged']['button'],
                ],
                ActionShowDocumentAsPaged(self)
            ),
            'single_scan': (
                [
                    widget_tree.get_object("buttonScan"),
                ],
                ActionSingleScan(self, config)
            ),
            'multi_scan': (
                [
                    gactions['scan_from_feeder'],
                ],
                ActionMultiScan(self, config)
            ),
            'import': (
                [
                    gactions['import']
                ],
                ActionImport(self, config)
            ),
            'print': (
                [
                    gactions['print'],
                ],
                ActionPrintDoc(self)
            ),
            'open_export_doc_dialog': (
                [
                    gactions['export_doc'],
                ],
                ActionOpenExportDocDialog(self)
            ),
            'open_export_page_dialog': (
                [
                    gactions['export_page'],
                ],
                ActionOpenExportPageDialog(self)
            ),
            'cancel_export': (
                [widget_tree.get_object("buttonCancelExport")],
                ActionCancelExport(self),
            ),
            'select_export_format': (
                [widget_tree.get_object("comboboxExportFormat")],
                ActionSelectExportFormat(self),
            ),
            'change_export_property': (
                [
                    widget_tree.get_object("scaleQuality"),
                    widget_tree.get_object("comboboxPageFormat"),
                ],
                ActionChangeExportProperty(self),
            ),
            'select_export_path': (
                [widget_tree.get_object("buttonSelectExportPath")],
                ActionSelectExportPath(self),
            ),
            'export': (
                [widget_tree.get_object("buttonExport")],
                ActionExport(self),
            ),
            'open_settings': (
                [
                    gactions['open_settings'],
                ],
                ActionOpenSettings(self, config)
            ),
            'quit': (
                [
                    gactions['quit'],
                ],
                ActionQuit(self, config),
            ),
            'create_label': (
                [
                    self.doc_properties_panel.widgets['button_add_label']
                ],
                ActionCreateLabel(self),
            ),
            # TODO
            #'del_label': (
            #    [
            #        widget_tree.get_object("menuitemDestroyLabel"),
            #        widget_tree.get_object("buttonDelLabel"),
            #    ],
            #    ActionDeleteLabel(self),
            #),
            'open_doc_dir': (
                [
                    gactions['open_doc_dir']
                ],
                ActionOpenDocDir(self),
            ),
            # TODO
            #'del_doc': (
            #    [
            #        widget_tree.get_object("menuitemDestroyDoc2"),
            #        widget_tree.get_object("toolbuttonDeleteDoc"),
            #    ],
            #    ActionDeleteDoc(self),
            #),
            # TODO
            #'edit_page': (
            #    [
            #        widget_tree.get_object("menuitemEditPage"),
            #        widget_tree.get_object("menuitemEditPage2"),
            #        widget_tree.get_object("toolbuttonEditPage"),
            #    ],
            #    ActionEditPage(self),
            #),
            # TODO
            'optimize_index': (
                [
                    gactions['optimize_index'],
                ],
                ActionOptimizeIndex(self),
            ),
            'set_current_page': (
                [
                    self.page_nb['current'],
                ],
                ActionOpenPageNb(self),
            ),
            'zoom_level': (
                [
                    self.zoom_level['model'],
                ],
                ActionUpdPageSizes(self)
            ),
            'search': (
                [
                    self.search_field,
                ],
                ActionUpdateSearchResults(self),
            ),
            # TODO
            #'switch_sorting': (
            #    [
            #        widget_tree.get_object("radiomenuitemSortByRelevance"),
            #        widget_tree.get_object("radiomenuitemSortByScanDate"),
            #    ],
            #    ActionSwitchSorting(self, config),
            #),
            # TODO
            #'toggle_label': (
            #    [
            #        widget_tree.get_object("cellrenderertoggleLabel"),
            #    ],
            #    ActionToggleLabel(self),
            #),
            'show_all_boxes': (
                [
                    widget_tree.get_object("show_all_boxes"),
                ],
                ActionToggleAllBoxes(self)
            ),
            'redo_ocr_doc': (
                [
                    gactions['redo_ocr_doc'],
                ],
                ActionRedoDocOCR(self),
            ),
            'redo_ocr_all': (
                [
                    gactions['redo_ocr_all'],
                ],
                ActionRedoAllOCR(self),
            ),
            'reindex_from_scratch': (
                [
                    gactions['reindex_all'],
                ],
                ActionRefreshIndex(self, config, force=True),
            ),
            'reindex': (
                [],
                ActionRefreshIndex(self, config, force=False),
            ),
            'about': (
                [
                    gactions['about'],
                ],
                ActionAbout(self),
            ),
        }

        connect_actions(self.actions)

        accelerators = [
            ('<Primary>e', 'clicked',
             widget_tree.get_object("toolbuttonEditDoc")),
            ('<Primary>n', 'clicked',
             widget_tree.get_object("toolbuttonNew")),
            ('<Primary>f', 'grab-focus',
             self.search_field),
        ]
        # TODO
        #accel_group = Gtk.AccelGroup()
        #for (shortcut, signame, widget) in accelerators:
        #    (key, mod) = Gtk.accelerator_parse(shortcut)
        #    widget.add_accelerator(signame, accel_group, key, mod,
        #                           Gtk.AccelFlags.VISIBLE)
        #self.window.add_accel_group(accel_group)

        self.need_doc_widgets = set(
            self.actions['print'][0]
            # TODO
            # + self.actions['create_label'][0]
            + self.actions['open_doc_dir'][0]
            # + self.actions['del_doc'][0]
            # + self.actions['set_current_page'][0]
            + self.actions['redo_ocr_doc'][0]
            + self.actions['open_export_doc_dialog'][0]
            # + self.actions['edit_doc'][0]
        )

        self.need_page_widgets = set(
            # TODO
            # self.actions['del_page'][0]
            self.actions['open_export_page_dialog'][0]
            # + self.actions['edit_page'][0]
        )

        self.doc_edit_widgets = set(
            # TODO
            self.actions['single_scan'][0]
            # + self.actions['del_page'][0]
            # + self.actions['edit_page'][0]
        )

        self.__show_all_boxes_widget = \
            self.actions['show_all_boxes'][0][0]

        set_widget_state(self.need_page_widgets, False)
        set_widget_state(self.need_doc_widgets, False)

        for (popup_menu_name, popup_menu) in self.popup_menus.iteritems():
            assert(not popup_menu[0] is None)
            assert(not popup_menu[1] is None)
            # TODO(Jflesch): Find the correct signal
            # This one doesn't take into account the key to access these menus
            popup_menu[0].connect("button-press-event", self.__popup_menu_cb,
                                  popup_menu[0], popup_menu[1])

        # TODO
        #self.lists['doclist']['gui'].connect(
        #    "drag-data-received", self.__on_doclist_drag_data_received_cb)

        self.window.connect("destroy",
                            ActionRealQuit(self, config).on_window_close_cb)

        self.img['viewport']['widget'].connect(None, "size-allocate",
                                               self.__on_img_area_resize_cb)
        self.window.connect("size-allocate", self.__on_window_resized_cb)

        self.window.set_visible(True)

        for scheduler in self.schedulers.values():
            scheduler.start()

    def __init_app(self):
        GLib.set_application_name(_("Paperwork"))
        GLib.set_prgname("paperwork")

        app = Gtk.Application(
            application_id=None,
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        app.register(None)
        Gtk.Application.set_default(app)
        return app

    def __init_gactions(self, app):
        gactions = {
            'about': Gio.SimpleAction.new("about", None),
            'export_doc': Gio.SimpleAction.new("export_doc", None),
            'export_page': Gio.SimpleAction.new("export_page", None),
            'import': Gio.SimpleAction.new("import", None),
            'open_settings': Gio.SimpleAction.new("settings", None),
            'open_doc_dir': Gio.SimpleAction.new("doc_open_dir", None),
            'optimize_index': Gio.SimpleAction.new("optimize_index", None),
            'print': Gio.SimpleAction.new("print", None),
            'redo_ocr_doc': Gio.SimpleAction.new("redo_ocr_doc", None),
            'redo_ocr_all': Gio.SimpleAction.new("redo_ocr_all", None),
            'reindex_all': Gio.SimpleAction.new("reindex_all", None),
            'scan_single': Gio.SimpleAction.new("scan_single_page", None),
            'scan_from_feeder': Gio.SimpleAction.new("scan_from_feeder", None),
            'quit': Gio.SimpleAction.new("quit", None),
        }
        for action in gactions.values():
            app.add_action(action)
        return gactions

    def __init_schedulers(self):
        return {
            'main': JobScheduler("Main"),
            'ocr': JobScheduler("OCR"),
            'page_boxes_loader': JobScheduler("Page boxes loader"),
            'progress': JobScheduler("Progress"),
            'scan': JobScheduler("Scan"),
        }

    def __init_default_thumbnail(self, width=BasicPage.DEFAULT_THUMB_WIDTH,
                                 height=BasicPage.DEFAULT_THUMB_HEIGHT):
        img = PIL.Image.new("RGB", (
            width,
            height,
        ), color="#EEEEEE")
        img = add_img_border(img, JobDocThumbnailer.THUMB_BORDER)
        return image2pixbuf(img)

    def __init_app_menu(self, app):
        app_menu = load_uifile(os.path.join("mainwindow", "appmenu.xml"))
        advanced_menu = app_menu.get_object("advanced")
        app.set_app_menu(app_menu.get_object("app-menu"))
        return advanced_menu

    def __init_window(self, widget_tree, config):
        window = widget_tree.get_object("mainWindow")
        window.set_application(self.app)
        window.set_default_size(config['main_win_size'].value[0],
                                config['main_win_size'].value[1])

        logo_path = os.path.join(sys.prefix, 'share', 'icons', 'paperwork.svg')
        if os.access(logo_path, os.F_OK):
            logo = GdkPixbuf.Pixbuf.new_from_file(logo_path)
            window.set_icon(logo)
        return window

    def set_search_availability(self, enabled):
        set_widget_state(self.doc_browsing.values(), enabled)

    def set_mouse_cursor(self, cursor):
        offset = {
            "Normal": -1,
            "Busy": 1
        }[cursor]

        self.__busy_mouse_counter += offset
        assert(self.__busy_mouse_counter >= 0)

        if self.__busy_mouse_counter > 0:
            cursor = Gdk.Cursor.new(Gdk.CursorType.WATCH)
        else:
            cursor = None
        self.window.get_window().set_cursor(cursor)

    def set_progression(self, src, progression, text):
        if progression > 0.0 or text is not None:
            self.progressbar.visible = True
            self.progressbar.set_progression(100 * progression, text)
        else:
            self.progressbar.visible = False
            self.progressbar.redraw()

    def set_zoom_level(self, level, auto=False):
        self.actions['zoom_level'][1].enabled = False
        self.zoom_level['model'].set_value(level)
        self.zoom_level['auto'] = auto
        self.actions['zoom_level'][1].enabled = True

    def on_index_loading_start_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(False)
        self.set_mouse_cursor("Busy")

    def on_index_loading_end_cb(self, src, docsearch):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")

        if docsearch is None:
            return

        self.docsearch = docsearch
        self.refresh_doc_list()
        self.refresh_label_list()

    def on_doc_examination_start_cb(self, src):
        self.set_progression(src, 0.0, None)

    def on_doc_examination_end_cb(self, src):
        self.set_progression(src, 0.0, None)

    def on_index_update_start_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Busy")

    def on_index_update_end_cb(self, src):
        self.schedulers['main'].cancel_all(
            self.job_factories['index_reloader'])

        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")
        gc.collect()

    def on_index_update_write_cb(self, src):
        self.set_search_availability(False)

    def _on_search_field_icon_activated(self, entry, icon_pos, event):
        if icon_pos != Gtk.EntryIconPosition.SECONDARY:
            return

    def on_search_start_cb(self):
        self.search_field.override_color(Gtk.StateFlags.NORMAL, None)

    def clear_doclist(self):
        self.lists['doclist']['gui'].freeze_child_notify()
        try:
            while True:
                row = self.lists['doclist']['gui'].get_row_at_index(0)
                if row is None:
                    break
                self.lists['doclist']['gui'].remove(row)

            self.lists['doclist']['model']['by_row'] = {}
            self.lists['doclist']['model']['by_id'] = {}
            self.lists['doclist']['model']['has_new'] = False
        finally:
            self.lists['doclist']['gui'].thaw_child_notify()

    def on_search_invalid_cb(self):
        self.schedulers['main'].cancel_all(
            self.job_factories['doc_thumbnailer'])
        self.search_field.override_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(red=1.0, green=0.0, blue=0.0, alpha=1.0)
        )
        self.clear_doclist()

    def switch_leftpane(self, to):
        for (name, revealers) in self.left_revealers.iteritems():
            visible = (to == name)
            for revealer in revealers:
                revealer.set_reveal_child(visible)

    def _make_listboxrow_doc_widget(self, doc, rowbox, selected=False):
        globalbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 10)

        # thumbnail
        thumbnail = Gtk.Image.new_from_pixbuf(self.default_small_thumbnail)
        thumbnail.set_size_request(self.SMALL_THUMBNAIL_WIDTH,
                                   self.SMALL_THUMBNAIL_HEIGHT)
        globalbox.add(thumbnail)

        internalbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 3)
        globalbox.add(internalbox)

        # doc name
        docname = Gtk.Label.new(doc.name)
        #docname.override_background_color(Gtk.StateFlags.NORMAL,
        #                                  Gdk.RGBA(1, 0, 1, 1))
        docname.set_justify(Gtk.Justification.LEFT)
        docname.set_halign(Gtk.Align.START)
        internalbox.add(docname)

        # doc labels
        labels = LabelWidget(doc.labels)
        labels.set_size_request(170, 10)
        #labels.override_background_color(Gtk.StateFlags.NORMAL,
        #                                 Gdk.RGBA(1, 0, 1, 1))
        internalbox.add(labels)


        # buttons
        button_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
        button_box.set_size_request(20, 40)
        button_box.set_homogeneous(True)
        #button_box.override_background_color(Gtk.StateFlags.NORMAL,
        #                                    Gdk.RGBA(1, 0, 1, 1))
        globalbox.pack_start(button_box, False, True, 0)

        edit_button = Gtk.Button.new_from_icon_name(
            "document-properties-symbolic",
            Gtk.IconSize.MENU)
        edit_button.set_relief(Gtk.ReliefStyle.NONE)
        edit_button.connect(
            "clicked",
            lambda _: GLib.idle_add(
                self.switch_leftpane, 'doc_properties'))

        button_box.add(edit_button)

        delete_button = Gtk.Button.new_from_icon_name(
            "edit-delete-symbolic",
            Gtk.IconSize.MENU)
        delete_button.set_relief(Gtk.ReliefStyle.NONE)
        delete_button.connect(
            "clicked",
            lambda _: GLib.idle_add(
                ActionDeleteDoc(self, doc).do))

        button_box.add(delete_button)

        for child in rowbox.get_children():
            rowbox.remove(child)
        rowbox.add(globalbox)
        rowbox.show_all()
        if not selected:
            delete_button.set_visible(False)
            edit_button.set_visible(False)

    def on_search_results_cb(self, search, documents):
        self.schedulers['main'].cancel_all(
            self.job_factories['doc_thumbnailer'])

        logger.debug("Got %d documents" % len(documents))

        self.clear_doclist()

        self.lists['doclist']['gui'].freeze_child_notify()
        try:
            for doc in documents:
                rowbox = Gtk.ListBoxRow()
                selected = (doc.docid == self.doc.docid)
                self._make_listboxrow_doc_widget(doc, rowbox, selected)
                self.lists['doclist']['model']['by_row'][rowbox] = doc.docid
                self.lists['doclist']['model']['by_id'][doc.docid] = rowbox
                self.lists['doclist']['gui'].add(rowbox)
        finally:
            self.lists['doclist']['gui'].thaw_child_notify()

        if search.strip() == u"":
            self.insert_new_doc()

        if self.doc.docid in self.lists['doclist']['model']['by_id']:
            row = self.lists['doclist']['model']['by_id'][self.doc.docid]
            self.lists['doclist']['gui'].select_row(row)

        job = self.job_factories['doc_thumbnailer'].make(documents)
        self.schedulers['main'].schedule(job)


    def on_search_suggestions_cb(self, suggestions):
        logger.debug("Got %d suggestions" % len(suggestions))
        self.lists['suggestions']['gui'].freeze_child_notify()
        try:
            self.lists['suggestions']['model'].clear()
            for suggestion in suggestions:
                self.lists['suggestions']['model'].append([suggestion])
        finally:
            self.lists['suggestions']['gui'].thaw_child_notify()

    def on_label_prediction_cb(self, doc, predicted_labels):
        label_model = self.lists['labels']['model']
        for label_line in xrange(0, len(label_model)):
            label = label_model[label_line][2]
            line_iter = label_model.get_iter(label_line)
            predicted = label.name in predicted_labels
            label_model.set_value(line_iter, 4, predicted)

    def on_doc_thumbnailing_start_cb(self, src):
        self.set_progression(src, 0.0, _("Loading thumbnails ..."))
        self.lists['doclist']['gui'].freeze_child_notify()

    def on_doc_thumbnailing_doc_done_cb(self, src, thumbnail,
                                        doc, doc_nb, total_docs):
        self.set_progression(src, ((float)(doc_nb+1) / total_docs),
                            _("Loading thumbnails ..."))
        row = self.lists['doclist']['model']['by_id'][doc.docid]
        box = row.get_children()[0]
        thumbnail_widget = box.get_children()[0]
        thumbnail_widget.set_from_pixbuf(thumbnail)

    def on_doc_thumbnailing_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.lists['doclist']['gui'].thaw_child_notify()

    def drop_boxes(self):
        self.img['boxes']['all'] = []
        self.img['boxes']['highlighted'] = []
        self.img['boxes']['visible'] = []

    def on_label_updating_start_cb(self, src):
        self.set_search_availability(False)
        self.set_mouse_cursor("Busy")

    def on_label_updating_doc_updated_cb(self, src, progression, doc_name):
        self.set_progression(src, progression,
                             _("Updating label (%s) ...") % (doc_name))

    def on_label_deletion_doc_updated_cb(self, src, progression, doc_name):
        self.set_progression(src, progression,
                             _("Deleting label (%s) ...") % (doc_name))

    def on_label_updating_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")
        self.refresh_label_list()
        self.refresh_doc_list()

    def on_redo_ocr_end_cb(self, src):
        pass

    def __popup_menu_cb(self, ev_component, event, ui_component, popup_menu):
        # we are only interested in right clicks
        if event.button != 3 or event.type != Gdk.EventType.BUTTON_PRESS:
            return
        popup_menu.popup(None, None, None, None, event.button, event.time)

    def __get_doc_model_line(self, doc):
        assert(doc is not None)
        if self.doc and self.doc == doc:
            # make sure we use the exact same instance everywhere
            doc = self.doc
        thumbnail = self.default_thumbnail
        if doc.nb_pages <= 0:
            thumbnail = None
        return ([
            doc.name,
            thumbnail,
            doc,
            doc.labels,
        ])

    def insert_new_doc(self):
        # append a new document to the list
        doc = ImgDoc(self.__config['workdir'].value)
        self.lists['doclist']['model']['has_new'] = True
        rowbox = Gtk.ListBoxRow()
        self._make_listboxrow_doc_widget(doc, rowbox, False)
        self.lists['doclist']['model']['by_row'][rowbox] = doc.docid
        self.lists['doclist']['model']['by_id'][doc.docid] = rowbox
        self.lists['doclist']['gui'].insert(rowbox, 0)
        if self.doc.is_new:
            self.lists['doclist']['gui'].select_row(rowbox)


    def refresh_docs(self, docs, redo_thumbnails=True):
        """
        Refresh specific documents in the document list

        Arguments:
            docs --- Array of Doc
        """
        for doc in docs:
            if doc.docid in self.lists['doclist']['model']['by_id']:
                rowbox = self.lists['doclist']['model']['by_id'][doc.docid]
                self._make_listboxrow_doc_widget(doc, rowbox,
                                                doc.docid == self.doc.docid)
            else:
                # refresh the whole list for now, it's much simpler
                self.refresh_doc_list()
                return

        # and rethumbnail what must be
        docs = [x for x in docs]
        logger.info("Will redo thumbnails: %s" % str(docs))
        job = self.job_factories['doc_thumbnailer'].make(docs)
        self.schedulers['main'].schedule(job)

    def refresh_doc_list(self):
        """
        Update the suggestions list and the matching documents list based on
        the keywords typed by the user in the search field.
        Warning: Will reset all the thumbnail to the default one
        """
        self.schedulers['main'].cancel_all(self.job_factories['searcher'])
        search = unicode(self.search_field.get_text(), encoding='utf-8')
        job = self.job_factories['searcher'].make(
            self.docsearch, self.get_doc_sorting()[1], search)
        self.schedulers['main'].schedule(job)

    def __get_page_model_line(self, page):
        if self.page and self.page == page:
            # always use the very same instance to avoid troubles
            page = self.page
        return [
            _('Page %d') % (page.page_nb + 1),
            self.default_thumbnail,
            page.page_nb
        ]

    def refresh_boxes(self):
        search = unicode(self.search_field.get_text(), encoding='utf-8')
        for page in self.page_drawers:
            page.show_all_boxes = self.show_all_boxes
            page.reload_boxes(search)

    def update_page_sizes(self):
        (auto, factor) = self.get_zoom_level()
        if auto:
            # compute the wanted factor
            factor = 1.0
            for page in self.page_drawers:
                factor = min(factor, self.compute_zoom_level(
                    page.max_size,
                    [drawer.page for drawer in self.page_drawers]))
            self.set_zoom_level(factor, auto=True)

        self.schedulers['main'].cancel_all(
            self.job_factories['page_img_loader']
        )
        self.schedulers['main'].cancel_all(
            self.job_factories['page_boxes_loader']
        )

        for page in self.page_drawers:
            page.set_size_ratio(factor)
            page.relocate()
        if self.doc.docid in self.scan_drawers:
            for drawer in self.scan_drawers[self.doc.docid].values():
                drawer.relocate()

    def __set_doc_buttons_visible(self, doc, visible):
        if (doc is None
                or not doc.docid in self.lists['doclist']['model']['by_id']
                or doc.is_new):
            return

        row = self.lists['doclist']['model']['by_id'][doc.docid]
        to_examine = row.get_children()
        while len(to_examine) > 0:
            widget = to_examine.pop()
            if type(widget) is Gtk.Button:
                widget.set_visible(visible)
            if hasattr(widget, 'get_children'):
                to_examine += widget.get_children()

    def set_layout(self, layout, force_refresh=True):
        if self.layout == layout:
            return
        self.layout = layout
        if force_refresh and self.doc is not None:
            self.show_doc(self.doc, force_refresh=True)
        img = {
            'grid': Gtk.Image.new_from_icon_name("view-grid-symbolic",
                                                 Gtk.IconSize.MENU),
            'paged': Gtk.Image.new_from_icon_name("view-paged-symbolic",
                                                  Gtk.IconSize.MENU),
        }[layout]
        self.layouts['settings_button'].set_image(img)

    def show_doc(self, doc, force_refresh=False):
        if (self.doc is not None
                and self.doc == doc
                and not force_refresh):
            logger.info("Doc is already shown")
            return

        logger.info("Showing document %s" % doc)
        previous_doc = self.doc
        self.doc = doc

        self.schedulers['main'].cancel_all(
            self.job_factories['page_img_loader']
        )
        self.schedulers['main'].cancel_all(
            self.job_factories['page_boxes_loader']
        )

        self.img['canvas'].remove_all_drawers()
        self.img['canvas'].add_drawer(self.progressbar)
        assert(self.progressbar.canvas)

        factories = {
            'page_img_loader': self.job_factories['page_img_loader'],
            'page_boxes_loader': self.job_factories['page_boxes_loader']
        }
        schedulers = {
            'page_img_loader': self.schedulers['main'],
            'page_boxes_loader': self.schedulers['page_boxes_loader'],
        }

        self.page_drawers = []
        scan_drawers = {}
        if self.doc.docid in self.scan_drawers:
            scan_drawers = self.scan_drawers[self.doc.docid]

        search = unicode(self.search_field.get_text(), encoding='utf-8')

        previous_drawer = None
        first_scan_drawer = None
        for page in doc.pages:
            if page.page_nb in scan_drawers:
                # scan drawers on existing pages ("redo OCR", etc)
                drawer = scan_drawers.pop(page.page_nb)
                drawer.previous_drawer = previous_drawer
                drawer.relocate()
                if not first_scan_drawer:
                    first_scan_drawer = drawer
            else:
                # normal pages
                drawer = PageDrawer(page, factories, schedulers,
                                    previous_drawer,
                                    show_boxes=(self.layout == 'paged'),
                                    show_border=(self.layout == 'grid'),
                                    show_all_boxes=self.show_all_boxes,
                                    enable_editor=(self.layout == 'paged'),
                                    sentence=search)
                drawer.connect("page-selected", self._on_page_drawer_selected)
                drawer.connect("page-edited", self._on_page_drawer_edited)
                drawer.connect("page-deleted", self._on_page_drawer_deleted)
            previous_drawer = drawer
            self.page_drawers.append(drawer)
            self.img['canvas'].add_drawer(drawer)

        for drawer in scan_drawers.values():
            # remaining scan drawers ("scan new page", etc)
            drawer.previous_drawer = previous_drawer
            drawer.relocate()
            self.page_drawers.append(drawer)
            self.img['canvas'].add_drawer(drawer)
            previous_drawer = drawer
            if not first_scan_drawer:
                first_scan_drawer = drawer

        # reset zoom level
        self.set_zoom_level(1.0, auto=True)
        self.update_page_sizes()
        self.img['canvas'].recompute_size()
        self.img['canvas'].upd_adjustments()

        is_new = doc.is_new
        can_edit = doc.can_edit

        set_widget_state(self.need_doc_widgets, not is_new)
        set_widget_state(self.need_page_widgets,
                         not is_new and self.layout == 'paged')
        set_widget_state(self.doc_edit_widgets, can_edit)

        # TODO
        #pages_gui = self.lists['pages']['gui']
        #if doc.can_edit:
        #    pages_gui.enable_model_drag_source(0, [], Gdk.DragAction.MOVE)
        #    pages_gui.drag_source_add_text_targets()
        #else:
        #    pages_gui.unset_model_drag_source()
        self.refresh_label_list()
        self.refresh_header_bar()

        self.__set_doc_buttons_visible(previous_doc, False)
        self.__set_doc_buttons_visible(self.doc, True)
        self.doc_properties_panel.set_doc(doc)

        if first_scan_drawer:
            # focus on the activity
            self.img['canvas'].get_vadjustment().set_value(
                    first_scan_drawer.position[1])

    def refresh_header_bar(self):
        # Pages
        if self.doc.nb_pages > 0:
            page = self.doc.pages[0]
        else:
            page = DummyPage(self.doc)
        self.show_page(page)
        self.__select_page(page)
        self.page_nb['total'].set_text(_("/ %d") % (self.doc.nb_pages))

        # Title
        self.headerbars['right'].set_title(self.doc.name)


    def show_page(self, page, force_refresh=False):
        if page is None:
            return

        if (page.doc != self.doc or force_refresh):
            self.show_doc(page.doc, force_refresh)

        logging.info("Showing page %s" % page)
        self.page = page

        drawer = None
        for d in self.page_drawers:
            if d.page == page:
                drawer = d
                break

        if drawer is not None:
            self.img['canvas'].get_vadjustment().set_value(
                drawer.position[1] - drawer.MARGIN
            )

        if self.export['exporter'] is not None:
            logging.info("Canceling export")
            self.actions['cancel_export'][1].do()

        self.export['dialog'].set_visible(False)

        set_widget_state(self.need_page_widgets, self.layout == 'paged')
        self.img['canvas'].redraw()

    def _on_page_drawer_selected(self, page_drawer):
        self.set_layout('paged', force_refresh=False)
        self.show_page(page_drawer.page, force_refresh=True)

    def _on_page_drawer_edited(self, page_drawer, actions):
        page = page_drawer.page
        img = page.img
        for action in actions:
            img = action.do(img)
        page.img = img  # will save the new image

        ActionRedoPageOCR(self).do(page)
        self.refresh_docs([page.doc])

    def _on_page_drawer_deleted(self, page_drawer):
        ActionDeletePage(self).do(page_drawer.page)

    def refresh_label_list(self):
        self.doc_properties_panel.refresh_label_list()

    def on_export_preview_start(self):
        visible = self.img['canvas'].visible_size
        spinner = SpinnerAnimation(
            ((visible[0] - SpinnerAnimation.ICON_SIZE) / 2,
             (visible[1] - SpinnerAnimation.ICON_SIZE) / 2)
        )

        self.img['canvas'].add_drawer(spinner)
        self.export['estimated_size'].set_text(_("Computing ..."))

    def on_export_preview_done(self, img_size, drawer):
        self.img['canvas'].remove_all_drawers()
        self.img['canvas'].add_drawer(self.progressbar)
        self.img['canvas'].add_drawer(drawer)

        self.export['estimated_size'].set_text(sizeof_fmt(img_size))

    def __get_img_area_width(self):
        w = self.img['viewport']['widget'].get_allocation().width
        w -= 2 * PageDrawer.MARGIN
        return w

    def __get_img_area_height(self):
        h = self.img['viewport']['widget'].get_allocation().height
        h -= 2 * PageDrawer.MARGIN
        return h

    def get_zoom_level(self):
        return (self.zoom_level['auto'], self.zoom_level['model'].get_value())

    def compute_zoom_level(self, img_size, other_pages):
        if self.layout == "grid":
            # see if we could fit all the pages on one line
            total_width = sum([page.size[0] for page in other_pages])
            canvas_width = self.img['canvas'].visible_size[0]
            canvas_width -= len(other_pages) * (2 * PageDrawer.MARGIN)
            factor = (float(canvas_width) / float(total_width))
            expected_width = img_size[0] * factor
            expected_height = img_size[0] * factor
            if (expected_width > BasicPage.DEFAULT_THUMB_WIDTH
                    and expected_height > BasicPage.DEFAULT_THUMB_HEIGHT):
                return factor

            # otherwise, fall back on the default size
            wanted_height = BasicPage.DEFAULT_THUMB_HEIGHT
            return float(wanted_height) / img_size[1]
        else:
            (auto, factor) = self.get_zoom_level()
            # factor is a postive float if user defined, 0 for full width and
            # -1 for full page
            if not auto:
                return factor
            wanted_width = self.__get_img_area_width()
            width_factor = float(wanted_width) / img_size[0]
            if factor == -1.0:
                wanted_height = self.__get_img_area_height()
                factor = min(width_factor, float(wanted_height) / img_size[1])
                return factor
            else:
                return width_factor

    def refresh_export_preview(self):
        self.img['canvas'].remove_all_drawers()
        self.img['canvas'].add_drawer(self.progressbar)
        self.schedulers['main'].cancel_all(
            self.job_factories['export_previewer']
        )
        job = self.job_factories['export_previewer'].make(
            self.export['exporter'])
        self.schedulers['main'].schedule(job)

    def __on_img_area_resize_cb(self, viewport, rectangle):
        if self.export['exporter'] is not None:
            return

        old_size = self.img['viewport']['size']
        new_size = (rectangle.width, rectangle.height)
        if old_size == new_size:
            return

        logger.info("Image view port resized. (%d, %d) --> (%d, %d)"
                    % (old_size[0], old_size[1], new_size[0], new_size[1]))
        self.img['viewport']['size'] = new_size

        (auto, factor) = self.get_zoom_level()
        if not auto:
            return

        self.update_page_sizes()

    def __on_page_list_drag_data_get_cb(self, widget, drag_context,
                                        selection_data, info, time):
        pageid = unicode(self.page.pageid)
        logger.info("[page list] drag-data-get: %s" % self.page.pageid)
        selection_data.set_text(pageid, -1)

    def __on_page_list_drag_data_received_cb(self, widget, drag_context, x, y,
                                             selection_data, info, time):
        target = self.lists['pages']['gui'].get_dest_item_at_pos(x, y)
        if target is None:
            logger.warning("[page list] drag-data-received: no target."
                           " aborting")
            drag_context.finish(False, False, time)
            return
        (target_path, position) = target
        if target_path is None:
            logger.warning("[page list] drag-data-received: no target."
                           " aborting")
            drag_context.finish(False, False, time)
            return
        target = target_path.get_indices()[0]
        target_idx = self.lists['pages']['model'][target][2]
        if position == Gtk.IconViewDropPosition.DROP_BELOW:
            target_idx += 1

        assert(target_idx >= 0)
        obj_id = selection_data.get_text()

        logger.info("[page list] drag-data-received: %s -> %s"
                    % (obj_id, target_idx))
        obj = self.docsearch.get_by_id(obj_id)
        if (target_idx >= obj.doc.nb_pages):
            target_idx = obj.doc.nb_pages - 1

        # TODO(Jflesch): Instantiate an ActionXXX to do that, so
        # this action can be cancelled later
        obj.change_index(target_idx)

        drag_context.finish(True, False, time)
        doc = obj.doc
        GLib.idle_add(self.refresh_docs, {doc})

    def __on_doclist_drag_data_received_cb(self, widget, drag_context, x, y,
                                              selection_data, info, time):
        obj_id = selection_data.get_text()
        # TODO
        #target = self.lists['doclist']['gui'].get_dest_item_at_pos(x, y)
        target = None
        if target is None:
            logger.warning("[doc list] drag-data-received: no target."
                           " aborting")
            drag_context.finish(False, False, time)
            return
        (target_path, position) = target
        if target_path is None:
            logger.warning("[doc list] drag-data-received: no target."
                           " aborting")
            drag_context.finish(False, False, time)
            return
        target = target_path.get_indices()[0]
        # TODO
        #target_doc = self.lists['doclist']['model'][target][2]
        target_doc = None
        obj_id = selection_data.get_text()
        obj = self.docsearch.get_by_id(obj_id)

        if not target_doc.can_edit:
            logger.warning("[doc list] drag-data-received:"
                           " Destination document can't be modified")
            drag_context.finish(False, False, time)
            return

        if target_doc == obj.doc:
            logger.info("[doc list] drag-data-received: Source and destination"
                        " docs are the same. Nothing to do")
            drag_context.finish(False, False, time)
            return

        logger.info("[doc list] drag-data-received: %s -> %s"
                    % (obj_id, target_doc.docid))
        # TODO(Jflesch): Instantiate an ActionXXX to do that, so
        # it can be cancelled later
        target_doc.steal_page(obj)

        if obj.doc.nb_pages <= 0:
            del_docs = {obj.doc.docid}
            upd_docs = {target_doc}
        else:
            del_docs = set()
            upd_docs = {obj.doc, target_doc}

        drag_context.finish(True, False, time)

        # the index update will start a doc list refresh when finished
        job = self.job_factories['index_updater'].make(
            docsearch=self.docsearch,
            new_docs=set(),
            upd_docs=upd_docs,
            del_docs=del_docs,
            optimize=False,
            reload_list=True
        )
        self.schedulers['main'].schedule(job)

    def __on_doc_lines_shown(self, docs):
        job = self.job_factories['doc_thumbnailer'].make(docs)
        self.schedulers['main'].schedule(job)

    def __on_window_resized_cb(self, _, rectangle):
        (w, h) = (rectangle.width, rectangle.height)
        self.__config['main_win_size'].value = (w, h)

    def get_doc_sorting(self):
        # TODO ?
        return ("scan_date", sort_documents_by_date)

    def __get_show_all_boxes(self):
        return self.__show_all_boxes_widget.get_active()

    def __set_show_all_boxes(self, value):
        self.__show_all_boxes_widget.set_active(boolean(value))

    show_all_boxes = property(__get_show_all_boxes, __set_show_all_boxes)

    def __select_page(self, page):
        set_widget_state(self.need_page_widgets, self.layout == 'paged')
        self.actions['set_current_page'][1].enabled = False
        self.page_nb['current'].set_text("%d" % (page.page_nb + 1))
        self.actions['set_current_page'][1].enabled = True

    def __on_img_window_moved(self):
        pos = self.img['canvas'].position
        size = self.img['canvas'].visible_size
        pos = (pos[0] + (size[0] / 2),
               pos[1] + (size[1] / 2))
        drawer = self.img['canvas'].get_drawer_at(pos)
        if drawer is None:
            return
        if not hasattr(drawer, 'page'):
            return
        page = drawer.page
        if page is None:
            set_widget_state(self.need_page_widgets, False)
            return
        self.__select_page(page)


    def make_scan_workflow(self):
        return ScanWorkflow(self.__config,
                            self.schedulers['scan'],
                            self.schedulers['ocr'])

    def make_scan_workflow_drawer(self, scan_workflow, single_angle=False,
                                  page=None):
        if single_angle:
            drawer = SingleAngleScanWorkflowDrawer(scan_workflow, page)
        else:
            drawer = MultiAnglesScanWorkflowDrawer(scan_workflow, page)
        # make sure the canvas is set even if we don't display it
        drawer.set_canvas(self.img['canvas'])
        return drawer

    def remove_scan_workflow(self, scan_workflow):
        for (docid, drawers) in self.scan_drawers.iteritems():
            for (page_nb, drawer) in drawers.iteritems():
                if (scan_workflow == drawer
                        or scan_workflow == drawer.scan_workflow):
                    drawers.pop(page_nb)
                    return docid
        raise ValueError("ScanWorkflow not found")

    def add_scan_workflow(self, doc, scan_workflow_drawer, page_nb=-1):
        if doc.docid not in self.scan_drawers:
            self.scan_drawers[doc.docid] = {}
        self.scan_drawers[doc.docid][page_nb] = scan_workflow_drawer

        if (self.doc.docid == doc.docid
                or (self.doc.is_new and doc.is_new)):
            self.page = None
            set_widget_state(self.need_page_widgets, False)
            self.show_doc(self.doc, force_refresh=True)

    def add_page(self, docid, img, line_boxes):
        doc = self.docsearch.get_doc_from_docid(docid)

        new = False
        if doc is None or doc.nb_pages <= 0:
            # new doc
            new = True
            if self.doc.is_new:
                doc = self.doc
            else:
                doc = ImgDoc(self.__config['workdir'].value)

        doc.add_page(img, line_boxes)
        doc.drop_cache()
        self.doc.drop_cache()

        if self.doc.docid == doc.docid:
            self.show_page(self.doc.pages[-1], force_refresh=True)

        if new:
            factory = self.job_factories['label_predictor_on_new_doc']
            job = factory.make(doc)
            job.connect("predicted-labels", lambda predictor, d, predicted:
                        GLib.idle_add(self.__on_predicted_labels, doc,
                                      predicted))
            self.schedulers['main'].schedule(job)
        else:
            self.upd_index(doc, new=False)

    def __on_predicted_labels(self, doc, predicted_labels):
        for label in self.docsearch.label_list:
            if label.name in predicted_labels:
                self.docsearch.add_label(doc, label, update_index=False)
        self.upd_index(doc, new=True)
        self.refresh_label_list()

    def upd_index(self, doc, new=False):
        self.refresh_docs({doc})
        if new:
            job = self.job_factories['index_updater'].make(
                self.docsearch, new_docs={doc}, optimize=False)
        else:
            job = self.job_factories['index_updater'].make(
                self.docsearch, upd_docs={doc}, optimize=False)
        self.schedulers['main'].schedule(job)
