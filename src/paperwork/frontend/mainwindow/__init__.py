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
from paperwork.frontend.doceditdialog import DocEditDialog
from paperwork.frontend.labeleditor import LabelEditor
from paperwork.frontend.mainwindow.pages import PageDrawer
from paperwork.frontend.mainwindow.pages import JobFactoryPageBoxesLoader
from paperwork.frontend.mainwindow.pages import JobFactoryPageImgLoader
from paperwork.frontend.mainwindow.scan import ScanWorkflow
from paperwork.frontend.mainwindow.scan import MultiAnglesScanWorkflowDrawer
from paperwork.frontend.mainwindow.scan import SingleAngleScanWorkflowDrawer
from paperwork.frontend.multiscan import MultiscanDialog
from paperwork.frontend.pageeditor import PageEditingDialog
from paperwork.frontend.settingswindow import SettingsWindow
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
from paperwork.frontend.util.jobs import Job, JobFactory, JobScheduler
from paperwork.frontend.util.jobs import JobFactoryProgressUpdater
from paperwork.frontend.util.progressivelist import ProgressiveList
from paperwork.frontend.util.renderer import CellRendererLabels
from paperwork.backend import docimport
from paperwork.backend.common.page import BasicPage, DummyPage
from paperwork.backend.docsearch import DocSearch
from paperwork.backend.docsearch import DummyDocSearch
from paperwork.backend.img.doc import ImgDoc

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

    def __refresh_docs(self, new_docs, upd_docs, del_docs, reload_all,
                       reload_thumbnails):
        if reload_all:
            job = self.__main_win.job_factories['index_reloader'].make()
            self.__main_win.schedulers['main'].schedule(job)
        else:
            docs = new_docs
            docs = docs.union(upd_docs)
            docs = docs.union(del_docs)
            self.__main_win.refresh_docs(docs,
                                         redo_thumbnails=reload_thumbnails)

    def make(self, docsearch,
             new_docs=set(), upd_docs=set(), del_docs=set(),
             optimize=True, reload_all=True, reload_thumbnails=True):
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
        job.connect('index-update-end',
                    lambda updater:
                    GLib.idle_add(self.__refresh_docs, new_docs, upd_docs,
                                  del_docs, reload_all, reload_thumbnails))
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


class JobPageThumbnailer(Job):
    """
    Generate page thumbnails
    """

    __gsignals__ = {
        'page-thumbnailing-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'page-thumbnailing-page-done': (GObject.SignalFlags.RUN_LAST, None,
                                        (GObject.TYPE_INT,
                                         GObject.TYPE_PYOBJECT)),
        'page-thumbnailing-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = True
    priority = 400

    def __init__(self, factory, id, doc, search):
        Job.__init__(self, factory, id)
        self.__doc = doc
        self.__search = search

        self.__current_idx = -1
        self.done = False

    def do(self):
        if self.done:
            return

        pages = self.__doc.pages
        nb_pages = self.__doc.nb_pages

        self.can_run = True
        if self.__current_idx >= nb_pages:
            return
        if not self.can_run:
            return

        if self.__current_idx < 0:
            self.emit('page-thumbnailing-start')
            self.__current_idx = 0

        for page_idx in xrange(self.__current_idx, nb_pages):
            page = pages[page_idx]
            img = page.get_thumbnail(BasicPage.DEFAULT_THUMB_WIDTH,
                                     BasicPage.DEFAULT_THUMB_HEIGHT)
            img = img.copy()

            if self.__search != u"" and self.__search in page:
                img = add_img_border(img, color="#009e00", width=3)
            else:
                img = add_img_border(img)
            if not self.can_run:
                return

            pixbuf = image2pixbuf(img)
            self.emit('page-thumbnailing-page-done', page_idx, pixbuf)
            self.__current_idx = page_idx
            if not self.can_run:
                return
        self.emit('page-thumbnailing-end')
        self.done = True

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()
        if (not will_resume
                and self.__current_idx >= 0
                and not self.done):
            self.done = True
            self.emit('page-thumbnailing-end')


GObject.type_register(JobPageThumbnailer)


class JobFactoryPageThumbnailer(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "PageThumbnailer")
        self.__main_win = main_win

    def make(self, doc, search):
        job = JobPageThumbnailer(self, next(self.id_generator), doc, search)
        job.connect('page-thumbnailing-start',
                    lambda thumbnailer:
                    GLib.idle_add(
                        self.__main_win.on_page_thumbnailing_start_cb,
                        thumbnailer))
        job.connect('page-thumbnailing-page-done',
                    lambda thumbnailer, page_idx, thumbnail:
                    GLib.idle_add(
                        self.__main_win.on_page_thumbnailing_page_done_cb,
                        thumbnailer, page_idx, thumbnail))
        job.connect('page-thumbnailing-end',
                    lambda thumbnailer:
                    GLib.idle_add(
                        self.__main_win.on_page_thumbnailing_end_cb,
                        thumbnailer))
        return job


class JobDocThumbnailer(Job):
    """
    Generate doc list thumbnails
    """

    THUMB_BORDER = 1

    __gsignals__ = {
        'doc-thumbnailing-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'doc-thumbnailing-doc-done': (GObject.SignalFlags.RUN_LAST, None,
                                      (GObject.TYPE_INT,  # doc idx in the list
                                       GObject.TYPE_PYOBJECT,
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
        if height > BasicPage.DEFAULT_THUMB_HEIGHT:
            img = img.crop((0, 0, width, BasicPage.DEFAULT_THUMB_HEIGHT))
            img = img.copy()
        else:
            new_img = PIL.Image.new(
                'RGBA', (width, BasicPage.DEFAULT_THUMB_HEIGHT),
                '#FFFFFF'
            )
            h = (BasicPage.DEFAULT_THUMB_HEIGHT - height) / 2
            new_img.paste(img, (0, h, width, h+height))
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
            (doc_position, doc) = self.__doclist[idx]
            if doc_position < 0:
                continue
            if doc.nb_pages <= 0:
                continue

            img = doc.pages[0].get_thumbnail(BasicPage.DEFAULT_THUMB_WIDTH,
                                             BasicPage.DEFAULT_THUMB_HEIGHT)
            if not self.can_run:
                return

            img = self.__resize(img)
            if not self.can_run:
                return

            img = add_img_border(img, width=self.THUMB_BORDER)
            if not self.can_run:
                return

            pixbuf = image2pixbuf(img)
            self.emit('doc-thumbnailing-doc-done', doc_position, pixbuf,
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
            lambda thumbnailer, doc_idx, thumbnail, doc_nb, total_docs:
            GLib.idle_add(self.__main_win.on_doc_thumbnailing_doc_done_cb,
                          thumbnailer, doc_idx, thumbnail, doc_nb,
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


class JobFactoryPageEditor(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "PageEditor")
        self.__main_win = main_win

    def make(self, page, changes):
        job = JobPageEditor(self, next(self.id_generator),
                            page, changes)
        job.connect('page-editing-img-edit',
                    lambda job, page:
                    GLib.idle_add(
                        self.__main_win.on_page_editing_img_edit_start_cb,
                        job, page))
        job.connect('page-editing-done',
                    lambda job, page:
                    GLib.idle_add(self.__main_win.on_page_editing_done_cb,
                                  job, page))
        return job


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
                optimize=False, reload_all=True, reload_thumbnails=True)
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

        doclist = self.__main_win.lists['doclist']
        if (len(doclist) <= 0):
            must_insert_new = True
        else:
            must_insert_new = not doclist[0].is_new

        if must_insert_new:
            self.__main_win.insert_new_doc()

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

        match_list = self.__main_win.lists['matches']['gui']
        selection_path = match_list.get_selected_items()
        if len(selection_path) <= 0:
            logger.info("No document selected. Can't open")
            return
        doc_idx = selection_path[0].get_indices()[0]
        doc = self.__main_win.lists['matches']['model'][doc_idx][2]

        logger.info("Showing doc %s" % doc)
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
            # Don't call self.__main_win.refresh_page_list():
            # it will redo the list from scratch. We just want to update
            # the thumbnails of the pages. There is no new or removed pages.
            self.__main_win.schedulers['main'].cancel_all(
                self.__main_win.job_factories['page_thumbnailer'])
            search = unicode(self.__main_win.search_field.get_text(),
                             encoding='utf-8')
            job = self.__main_win.job_factories['page_thumbnailer'].make(
                self.__main_win.doc, search)
            self.__main_win.schedulers['main'].schedule(job)

            self.__main_win.refresh_boxes()

    def on_icon_press_cb(self, entry, iconpos=Gtk.EntryIconPosition.SECONDARY,
                         event=None):
        if iconpos == Gtk.EntryIconPosition.PRIMARY:
            entry.grab_focus()
        else:
            entry.set_text("")


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


class ActionOpenPageSelected(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self,
                              "Show a page (selected from the page"
                              " thumbnail list)")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        gui_list = self.__main_win.lists['pages']['gui']
        selection_path = gui_list.get_selected_items()
        if len(selection_path) <= 0:
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
        self.__main_win.show_page(page, force_refresh=True)


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


class ActionUpdPageSizes(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Reload current page")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        mw = self.__main_win
        mw.update_page_sizes()
        mw.show_page(self.__main_win.page, force_refresh=True)
        self.__config['zoom_level'].value = mw.get_raw_zoom_level()


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
        self.__main_win.show_all_boxes = not self.__main_win.show_all_boxes
        self.__main_win.refresh_boxes()


class ActionLabelSelected(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Label selected")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        set_widget_state(self.__main_win.need_label_widgets, True)
        return True


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
            optimize=False, reload_all=False, reload_thumbnails=False)
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
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Editing label")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        label_list = self.__main_win.lists['labels']['gui']
        selection_path = label_list.get_selection().get_selected()
        if selection_path[1] is None:
            logger.warning("No label selected")
            return True
        label = selection_path[0].get_value(selection_path[1], 2)

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
        self.__main_win.refresh_page_list()
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
        dialog = Gtk.MessageDialog(parent=self.__main_win.window,
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
        dialog = Gtk.MessageDialog(parent=self.__main_win.window,
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
        doc = self.__main_win.doc
        docid = doc.docid

        self.__main_win.actions['new_doc'][1].do()

        logger.info("Deleting ...")
        doc.destroy()
        index_upd = self.__main_win.docsearch.get_index_updater(
            optimize=False)
        index_upd.del_doc(docid)
        index_upd.commit()
        logger.info("Deleted")

        # TODO(Jflesch): this should be the correct thing to do
        # self.__main_win.refresh_docs({doc})
        self.__main_win.refresh_doc_list()


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

        page = self.__main_win.page
        doc = page.doc

        SimpleAction.do(self)
        logger.info("Deleting ...")
        page.destroy()
        logger.info("Deleted")
        self.__main_win.page = None
        set_widget_state(self.__main_win.need_page_widgets, False)
        self.__main_win.refresh_docs({self.__main_win.doc})
        self.__main_win.refresh_page_list()
        self.__main_win.refresh_label_list()
        self.__main_win.show_doc(self.__main_win.doc, force_refresh=True)

        if doc.nb_pages <= 0:
            job = self.__main_win.job_factories['index_updater'].make(
                self.__main_win.docsearch, del_docs={doc.docid},
                optimize=False, reload_all=False, reload_thumbnails=False)
        else:
            job = self.__main_win.job_factories['index_updater'].make(
                self.__main_win.docsearch, upd_docs={doc}, optimize=False,
                reload_all=False, reload_thumbnails=False)
        self.__main_win.schedulers['main'].schedule(job)


class ActionRedoOCR(SimpleAction):
    def __init__(self, name, main_window):
        SimpleAction.__init__(self, name)
        self._main_win = main_window

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
            job = self._main_win.job_factories['index_updater'].make(
                self._main_win.docsearch, upd_docs=docs_done, optimize=False,
                reload_all=False, reload_thumbnails=False)
            self._main_win.schedulers['main'].schedule(job)

    def do(self, pages_iterator):
        if not ask_confirmation(self._main_win.window):
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
        ActionRedoOCR.__init__(self, "Redoing doc ocr", main_window)

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
        self.main_win.lists['zoom_levels']['gui'].set_sensitive(False)
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
                                        parent=self.__main_win.window,
                                        action=Gtk.FileChooserAction.SAVE,
                                        buttons=(Gtk.STOCK_CANCEL,
                                                 Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_SAVE,
                                                 Gtk.ResponseType.OK))
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
        self.main_win.lists['zoom_levels']['gui'].set_sensitive(True)
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


class ActionEditDoc(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Edit doc")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        DocEditDialog(self.__main_win, self.__config, self.__main_win.doc)


class ActionOptimizeIndex(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Optimize index")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        job = self.__main_win.job_factories['index_updater'].make(
            self.__main_win.docsearch, optimize=True,
            reload_all=False, reload_thumbnails=False)
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
            reload_all=True, reload_thumbnails=True
        )
        self.__main_win.schedulers['main'].schedule(job)


class ActionEditPage(SimpleAction):
    """
    Open the dialog to edit a page
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Edit page")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        ped = PageEditingDialog(self.__main_win, self.__main_win.page)
        todo = ped.get_changes()
        if todo == []:
            return
        logger.info("Changes to do to the page %s:" % (self.__main_win.page))
        for action in todo:
            logger.info("- %s" % action)

        job = self.__main_win.job_factories['page_editor'].make(
            self.__main_win.page, changes=todo)
        job.connect("page-editing-done", lambda job, page:
                    GLib.idle_add(self.__do_ocr, page))
        self.__main_win.schedulers['main'].schedule(job)

    def __do_ocr(self, page):
        logger.info("Redoing OCR on %s" % str(page))
        scan_workflow = self.__main_win.make_scan_workflow()
        drawer = self.__main_win.make_scan_workflow_drawer(
            scan_workflow, single_angle=True, page=page)
        self.__main_win.add_scan_workflow(page.doc, drawer,
                                          page_nb=page.page_nb)
        scan_workflow.connect('process-done',
                              lambda scan_workflow, img, boxes:
                              GLib.idle_add(self.__on_page_ocr_done,
                                            scan_workflow,
                                            img, boxes, page))
        scan_workflow.ocr(page.img, angles=1)

    def __on_page_ocr_done(self, scan_workflow, img, boxes, page):
        page.img = img
        page.boxes = boxes

        docid = self.__main_win.remove_scan_workflow(scan_workflow)
        if self.__main_win.doc.docid == page.doc.docid:
            self.__main_win.show_page(page, force_refresh=True)

        doc = self.__main_win.docsearch.get_doc_from_docid(docid)

        job = self.__main_win.job_factories['index_updater'].make(
            self.__main_win.docsearch, upd_docs={doc}, optimize=False,
            reload_all=False, reload_thumbnails=True)
        self.__main_win.schedulers['main'].schedule(job)


class MainWindow(object):
    PAGE_MARGIN = 50

    def __init__(self, config):
        self.app = self.__init_app()
        gactions = self.__init_gactions(self.app)

        self.schedulers = self.__init_schedulers()
        self.default_thumbnail = self.__init_default_thumbnail()

        # used by the set_mouse_cursor() function to keep track of how many
        # threads / jobs requested a busy mouse cursor
        self.__busy_mouse_counter = 0

        (self.__advanced_menu, self.__show_all_boxes_widget) = \
            self.__init_app_menu(self.app)

        widget_tree = load_uifile(
            os.path.join("mainwindow", "mainwindow.glade"))

        self.window = self.__init_window(widget_tree, config)

        iconview_matches = widget_tree.get_object("iconviewMatch")
        cellrenderer_labels = CellRendererLabels()
        cellrenderer_labels.set_property('xpad', 10)
        cellrenderer_labels.set_property('ypad', 0)
        iconview_matches.pack_end(cellrenderer_labels, True)
        iconview_matches.add_attribute(cellrenderer_labels, 'labels', 3)

        label_column = widget_tree.get_object("treeviewcolumnLabels")
        cellrenderer_labels = CellRendererLabels()
        cellrenderer_labels.set_property('xpad', 0)
        cellrenderer_labels.set_property('ypad', 0)
        label_column.pack_end(cellrenderer_labels, True)
        label_column.add_attribute(cellrenderer_labels, 'labels', 0)
        label_column.add_attribute(cellrenderer_labels, 'highlight', 4)

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
        self.scan_drawers = {}  # docid --> [(page_nb, extra drawers]

        search_completion = Gtk.EntryCompletion()

        open_doc_action = ActionOpenSelectedDocument(self)
        open_page_action = ActionOpenPageSelected(self)

        self.lists = {
            'suggestions': {
                'gui': widget_tree.get_object("entrySearch"),
                'completion': search_completion,
                'model': widget_tree.get_object("liststoreSuggestion")
            },
            'doclist': [],
            'matches': ProgressiveList(
                name='documents',
                scheduler=self.schedulers['main'],
                default_thumbnail=self.default_thumbnail,
                gui=widget_tree.get_object("iconviewMatch"),
                scrollbars=widget_tree.get_object("scrolledwindowMatch"),
                model=widget_tree.get_object("liststoreMatch"),
                model_nb_columns=4,
                actions=[open_doc_action],
            ),
            'pages': ProgressiveList(
                name='pages',
                scheduler=self.schedulers['main'],
                default_thumbnail=self.default_thumbnail,
                gui=widget_tree.get_object("iconviewPage"),
                scrollbars=widget_tree.get_object("scrolledwindowPage"),
                model=widget_tree.get_object("liststorePage"),
                model_nb_columns=3,
                actions=[open_page_action],
            ),
            'labels': {
                'gui': widget_tree.get_object("treeviewLabel"),
                'model': widget_tree.get_object("liststoreLabel"),
            },
            'zoom_levels': {
                'gui': widget_tree.get_object("comboboxZoom"),
                'model': widget_tree.get_object("liststoreZoom"),
            },
        }

        self.lists['matches'].connect(
            'lines-shown',
            lambda x, docs: GLib.idle_add(self.__on_doc_lines_shown, docs))

        search_completion.set_model(self.lists['suggestions']['model'])
        search_completion.set_text_column(0)
        search_completion.set_match_func(lambda a, b, c, d: True, None)
        self.lists['suggestions']['gui'].set_completion(search_completion)

        self.indicators = {
            'current_page': widget_tree.get_object("entryPageNb"),
            'total_pages': widget_tree.get_object("labelTotalPages"),
        }

        self.search_field = widget_tree.get_object("entrySearch")
        # done here instead of mainwindow.glade so it can be translated
        self.search_field.set_placeholder_text(_("Search"))

        self.doc_browsing = {
            'matches': widget_tree.get_object("iconviewMatch"),
            'pages': widget_tree.get_object("iconviewPage"),
            'labels': widget_tree.get_object("treeviewLabel"),
            'search': self.search_field,
        }

        img_scrollbars = widget_tree.get_object("scrolledwindowPageImg")
        img_widget = Canvas(img_scrollbars)
        img_widget.set_visible(True)
        img_scrollbars.add(img_widget)

        img_widget.connect(
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

        self.status = {
            'progress': widget_tree.get_object("progressbar"),
            'text': widget_tree.get_object("statusbar"),
        }

        self.popup_menus = {
            'labels': (
                widget_tree.get_object("treeviewLabel"),
                widget_tree.get_object("popupmenuLabels")
            ),
            'matches': (
                widget_tree.get_object("iconviewMatch"),
                widget_tree.get_object("popupmenuMatchs")
            ),
            'pages': (
                widget_tree.get_object("iconviewPage"),
                widget_tree.get_object("popupmenuPages")
            ),
            'page': (
                img_widget,
                widget_tree.get_object("popupmenuPage")
            ),
        }

        self.show_all_boxes = False

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

        self.sortings = [
            (widget_tree.get_object("radiomenuitemSortByRelevance"),
             lambda docs: None, "relevance"),
            (widget_tree.get_object("radiomenuitemSortByScanDate"),
             sort_documents_by_date, "scan_date"),
        ]

        config_sorting_name = config['result_sorting'].value
        for (sorting_widget, unused, sorting_name) in self.sortings:
            if sorting_name == config_sorting_name:
                sorting_widget.set_active(True)

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
            'match_list': self.lists['matches'].job_factory,
            'page_editor': JobFactoryPageEditor(self, config),
            'page_img_renderer': JobFactoryPageImgRenderer(),
            'page_list': self.lists['pages'].job_factory,
            'page_img_loader': JobFactoryPageImgLoader(),
            'page_boxes_loader': JobFactoryPageBoxesLoader(),
            'page_thumbnailer': JobFactoryPageThumbnailer(self),
            'progress_updater': JobFactoryProgressUpdater(
                self.status['progress']),
            'searcher': JobFactoryDocSearcher(self, config),
        }

        self.actions = {
            'new_doc': (
                [
                    widget_tree.get_object("toolbuttonNew"),
                ],
                ActionNewDocument(self, config),
            ),
            'open_doc': (
                [
                    widget_tree.get_object("iconviewMatch"),
                ],
                open_doc_action,
            ),
            'open_page': (
                [
                    widget_tree.get_object("iconviewPage"),
                ],
                open_page_action,
            ),
            'select_label': (
                [
                    widget_tree.get_object("treeviewLabel"),
                ],
                ActionLabelSelected(self)
            ),
            'single_scan': (
                [
                    widget_tree.get_object("toolbuttonScan"),
                    widget_tree.get_object("menuitemScanSingle"),
                ],
                ActionSingleScan(self, config)
            ),
            'multi_scan': (
                [
                    widget_tree.get_object("menuitemScanFeeder"),
                ],
                ActionMultiScan(self, config)
            ),
            'import': (
                [
                    widget_tree.get_object("menuitemImport"),
                ],
                ActionImport(self, config)
            ),
            'print': (
                [
                    widget_tree.get_object("menuitemPrint1"),
                    widget_tree.get_object("toolbuttonPrint"),
                ],
                ActionPrintDoc(self)
            ),
            'open_export_doc_dialog': (
                [
                    widget_tree.get_object("menuitemExportDoc"),
                    widget_tree.get_object("menuitemExportDoc1"),
                ],
                ActionOpenExportDocDialog(self)
            ),
            'open_export_page_dialog': (
                [
                    widget_tree.get_object("menuitemExportPage"),
                    widget_tree.get_object("menuitemExportPage1"),
                    widget_tree.get_object("menuitemExportPage3"),
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
                    widget_tree.get_object("toolbuttonSettings"),
                ],
                ActionOpenSettings(self, config)
            ),
            'quit': (
                [
                    gactions['quit'],
                    widget_tree.get_object("toolbuttonQuit"),
                ],
                ActionQuit(self, config),
            ),
            'create_label': (
                [
                    widget_tree.get_object("buttonAddLabel"),
                    widget_tree.get_object("menuitemAddLabel"),
                ],
                ActionCreateLabel(self),
            ),
            'edit_label': (
                [
                    widget_tree.get_object("menuitemEditLabel"),
                    widget_tree.get_object("buttonEditLabel"),
                ],
                ActionEditLabel(self),
            ),
            'del_label': (
                [
                    widget_tree.get_object("menuitemDestroyLabel"),
                    widget_tree.get_object("buttonDelLabel"),
                ],
                ActionDeleteLabel(self),
            ),
            'open_doc_dir': (
                [
                    widget_tree.get_object("menuitemOpenDocDir"),
                    widget_tree.get_object("toolbuttonOpenDocDir"),
                ],
                ActionOpenDocDir(self),
            ),
            'del_doc': (
                [
                    widget_tree.get_object("menuitemDestroyDoc2"),
                    widget_tree.get_object("toolbuttonDeleteDoc"),
                ],
                ActionDeleteDoc(self),
            ),
            'edit_page': (
                [
                    widget_tree.get_object("menuitemEditPage"),
                    widget_tree.get_object("menuitemEditPage2"),
                    widget_tree.get_object("toolbuttonEditPage"),
                ],
                ActionEditPage(self),
            ),
            'del_page': (
                [
                    widget_tree.get_object("menuitemDestroyPage1"),
                    widget_tree.get_object("menuitemDestroyPage2"),
                    widget_tree.get_object("buttonDeletePage"),
                ],
                ActionDeletePage(self),
            ),
            'optimize_index': (
                [
                    gactions['optimize_index'],
                ],
                ActionOptimizeIndex(self),
            ),
            'prev_page': (
                [
                    widget_tree.get_object("toolbuttonPrevPage"),
                ],
                ActionMovePageIndex(self, True, -1),
            ),
            'next_page': (
                [
                    widget_tree.get_object("toolbuttonNextPage"),
                ],
                ActionMovePageIndex(self, True, 1),
            ),
            'set_current_page': (
                [
                    widget_tree.get_object("entryPageNb"),
                ],
                ActionOpenPageNb(self),
            ),
            'zoom_levels': (
                [
                    widget_tree.get_object("comboboxZoom"),
                ],
                ActionUpdPageSizes(self, config)
            ),
            'search': (
                [
                    self.search_field,
                ],
                ActionUpdateSearchResults(self),
            ),
            'switch_sorting': (
                [
                    widget_tree.get_object("radiomenuitemSortByRelevance"),
                    widget_tree.get_object("radiomenuitemSortByScanDate"),
                ],
                ActionSwitchSorting(self, config),
            ),
            'toggle_label': (
                [
                    widget_tree.get_object("cellrenderertoggleLabel"),
                ],
                ActionToggleLabel(self),
            ),
            'show_all_boxes': (
                [
                    gactions['show_all_boxes'],
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
            'edit_doc': (
                [
                    widget_tree.get_object("toolbuttonEditDoc"),
                    widget_tree.get_object("menuitemEditDoc")
                ],
                ActionEditDoc(self, config),
            ),
            'about': (
                [
                    gactions['about'],
                ],
                ActionAbout(self),
            ),
        }

        for action in self.actions:
            for button in self.actions[action][0]:
                if button is None:
                    logger.error("MISSING BUTTON: %s" % (action))
            self.actions[action][1].connect(self.actions[action][0])

        for (buttons, action) in self.actions.values():
            for button in buttons:
                if isinstance(button, Gtk.ToolButton):
                    button.set_tooltip_text(button.get_label())

        for button in self.actions['single_scan'][0]:
            # let's be more specific on the tool tips of these buttons
            if isinstance(button, Gtk.ToolButton):
                button.set_tooltip_text(_("Scan single page"))

        accelerators = [
            ('<Primary>e', 'clicked',
             widget_tree.get_object("toolbuttonEditDoc")),
            ('<Primary>n', 'clicked',
             widget_tree.get_object("toolbuttonNew")),
            ('<Primary>f', 'grab-focus',
             self.search_field),
        ]
        accel_group = Gtk.AccelGroup()
        for (shortcut, signame, widget) in accelerators:
            (key, mod) = Gtk.accelerator_parse(shortcut)
            widget.add_accelerator(signame, accel_group, key, mod,
                                   Gtk.AccelFlags.VISIBLE)
        self.window.add_accel_group(accel_group)

        self.need_doc_widgets = set(
            self.actions['print'][0]
            + self.actions['create_label'][0]
            + self.actions['open_doc_dir'][0]
            + self.actions['del_doc'][0]
            + self.actions['set_current_page'][0]
            + [self.lists['labels']['gui']]
            + self.actions['redo_ocr_doc'][0]
            + self.actions['open_export_doc_dialog'][0]
            + self.actions['edit_doc'][0]
        )

        self.need_page_widgets = set(
            self.actions['del_page'][0]
            + self.actions['prev_page'][0]
            + self.actions['next_page'][0]
            + self.actions['open_export_page_dialog'][0]
            + self.actions['edit_page'][0]
        )

        self.need_label_widgets = set(
            self.actions['del_label'][0]
            + self.actions['edit_label'][0]
        )

        self.doc_edit_widgets = set(
            self.actions['single_scan'][0]
            + self.actions['del_page'][0]
            + self.actions['edit_page'][0]
        )

        set_widget_state(self.need_page_widgets, False)

        for (popup_menu_name, popup_menu) in self.popup_menus.iteritems():
            assert(not popup_menu[0] is None)
            assert(not popup_menu[1] is None)
            # TODO(Jflesch): Find the correct signal
            # This one doesn't take into account the key to access these menus
            popup_menu[0].connect("button-press-event", self.__popup_menu_cb,
                                  popup_menu[0], popup_menu[1])

        for widget in [self.lists['pages']['gui'],
                       self.lists['matches']['gui']]:
            widget.enable_model_drag_dest([], Gdk.DragAction.MOVE)
            widget.drag_dest_add_text_targets()

        self.set_raw_zoom_level(config['zoom_level'].value)

        self.lists['pages']['gui'].connect(
            "drag-data-get", self.__on_page_list_drag_data_get_cb)
        self.lists['pages']['gui'].connect(
            "drag-data-received", self.__on_page_list_drag_data_received_cb)
        self.lists['matches']['gui'].connect(
            "drag-data-received", self.__on_match_list_drag_data_received_cb)

        self.window.connect("destroy",
                            ActionRealQuit(self, config).on_window_close_cb)

        self.img['viewport']['widget'].connect("size-allocate",
                                               self.__on_img_resize_cb)
        self.window.connect("size-allocate", self.__on_window_resized_cb)

        self.window.set_visible(True)

        for scheduler in self.schedulers.values():
            scheduler.start()

    def __init_app(self):
        GLib.set_application_name(_("Paperwork"))
        GLib.set_prgname("paperwork")

        app = Gtk.Application(
            application_id="app.paperwork",
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        app.register(None)
        Gtk.Application.set_default(app)
        return app

    def __init_gactions(self, app):
        gactions = {
            'about': Gio.SimpleAction.new("about", None),
            'open_settings': Gio.SimpleAction.new("settings", None),
            'optimize_index': Gio.SimpleAction.new("optimize_index", None),
            'show_all_boxes': Gio.SimpleAction.new("show_all_boxes", None),
            'redo_ocr_doc': Gio.SimpleAction.new("redo_ocr_doc", None),
            'redo_ocr_all': Gio.SimpleAction.new("redo_ocr_all", None),
            'reindex_all': Gio.SimpleAction.new("reindex_all", None),
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

    def __init_default_thumbnail(self):
        img = PIL.Image.new("RGB", (
            BasicPage.DEFAULT_THUMB_WIDTH,
            BasicPage.DEFAULT_THUMB_HEIGHT,
        ), color="#EEEEEE")
        img = add_img_border(img, JobDocThumbnailer.THUMB_BORDER)
        return image2pixbuf(img)

    def __init_app_menu(self, app):
        app_menu = load_uifile(os.path.join("mainwindow", "appmenu.xml"))
        advanced_menu = app_menu.get_object("advanced")
        show_all_boxes_widget = Gio.MenuItem.new(
            "XXX", "app.show_all_boxes")
        advanced_menu.insert_item(0, show_all_boxes_widget)
        app.set_app_menu(app_menu.get_object("app-menu"))
        return (advanced_menu, show_all_boxes_widget)

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
        context_id = self.status['text'].get_context_id(str(src))
        self.status['text'].pop(context_id)
        if (text is not None and text != ""):
            self.status['text'].push(context_id, text)
        self.status['progress'].set_fraction(progression)

    def set_raw_zoom_level(self, level):
        zoom_liststore = self.lists['zoom_levels']['model']

        new_idx = -1
        for zoom_idx in range(0, len(zoom_liststore)):
            if (zoom_liststore[zoom_idx][1] == level):
                new_idx = zoom_idx
                break
        if new_idx < 0:
            logger.warning("Unknown zoom level: %f" % level)
            return

        self.lists['zoom_levels']['gui'].set_active(new_idx)

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

    def on_search_start_cb(self):
        self.search_field.override_color(Gtk.StateFlags.NORMAL, None)

    def on_search_invalid_cb(self):
        self.schedulers['main'].cancel_all(
            self.job_factories['doc_thumbnailer'])
        self.search_field.override_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(red=1.0, green=0.0, blue=0.0, alpha=1.0)
        )
        self.lists['doclist'] = []
        self.lists['matches'].set_model([])

    def on_search_results_cb(self, search, documents):
        self.schedulers['main'].cancel_all(
            self.job_factories['doc_thumbnailer'])

        logger.debug("Got %d documents" % len(documents))

        if search == u"":
            new_doc = self.get_new_doc()
            documents = [new_doc] + documents

        doc_cp = []
        for doc in documents:
            if doc == self.doc:
                doc = self.doc
            doc_cp.append(doc)
        documents = doc_cp

        active_idx = -1
        idx = 0
        for doc in documents:
            if doc == self.doc:
                active_idx = idx
                break
            idx += 1

        if len(documents) > 0 and documents[0].is_new and self.doc.is_new:
            active_idx = 0

        self.lists['doclist'] = documents
        self.lists['matches'].set_model([self.__get_doc_model_line(doc)
                                         for doc in documents])
        self.lists['matches'].select_idx(active_idx)

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

    def on_page_thumbnailing_start_cb(self, src):
        self.set_progression(src, 0.0, _("Loading thumbnails ..."))
        self.set_mouse_cursor("Busy")

    def on_page_thumbnailing_page_done_cb(self, src, page_idx, thumbnail):
        if page_idx == self.page.page_nb:
            self.__select_page(self.page)
        self.lists['pages'].set_model_value(page_idx, 1, thumbnail)
        self.set_progression(src, ((float)(page_idx+1) / self.doc.nb_pages),
                             _("Loading thumbnails ..."))

    def on_page_thumbnailing_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")

    def on_doc_thumbnailing_start_cb(self, src):
        self.set_progression(src, 0.0, _("Loading thumbnails ..."))

    def on_doc_thumbnailing_doc_done_cb(self, src, doc_idx, thumbnail,
                                        doc_nb, total_docs):
        self.lists['matches'].set_model_value(doc_idx, 1, thumbnail)
        self.set_progression(src, ((float)(doc_nb+1) / total_docs),
                             _("Loading thumbnails ..."))

    def on_doc_thumbnailing_end_cb(self, src):
        self.set_progression(src, 0.0, None)

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
        self.refresh_label_list()

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

    def __pop_new_doc(self):
        doc_list = self.lists['doclist']
        if (len(doc_list) <= 0 or not doc_list[0].is_new):
            return None
        doc = doc_list[0]
        doc_list.pop(0)
        self.lists['matches'].pop(0)
        return doc

    def __insert_doc(self, doc_idx, doc):
        doc_list = self.lists['doclist']
        doc_list.insert(doc_idx, doc)
        doc_line = self.__get_doc_model_line(doc)
        self.lists['matches'].insert(doc_idx, doc_line)

    def __remove_doc(self, doc_idx):
        doc_list = self.lists['doclist']
        doc_list.pop(doc_idx)
        self.lists['matches'].pop(doc_idx)

    def get_new_doc(self):
        if not self.new_doc.is_new:
            self.new_doc = ImgDoc(self.__config['workdir'].value)
        return self.new_doc

    def insert_new_doc(self):
        # append a new document to the list
        doc_list = self.lists['doclist']
        new_doc = self.get_new_doc()
        doc_list.insert(0, new_doc)
        new_doc_line = self.__get_doc_model_line(new_doc)
        self.lists['matches'].insert(0, new_doc_line)

    def refresh_docs(self, docs, redo_thumbnails=True):
        """
        Refresh specific documents in the document list

        Arguments:
            docs --- Array of Doc
        """
        must_rethumbnail = set()

        for doc in set(docs):
            try:
                if doc.is_new:  # ASSUMPTION: was actually deleted
                    doc_list = self.lists['doclist']
                    idx = doc_list.index(doc)
                    logger.info("Doc list refresh: %d:%s deleted"
                                % (idx, doc.docid))
                    self.__remove_doc(idx)
                    docs.remove(doc)
            except ValueError:
                logger.warning("Unable to find doc [%s] in the list"
                               % str(doc))

        new_doc = self.__pop_new_doc()
        if new_doc:
            logger.debug("Doc list refresh: 'new doc' (%s) popped out"
                         " of the  list" % new_doc)

        # make sure all the target docs are already in the list in a first
        # place
        # XXX(Jflesch): this may screw up the document sorting
        doc_list = self.lists['doclist']
        doc_list = {doc_list[x]: x for x in xrange(0, len(doc_list))}
        for doc in set(docs):
            if doc not in doc_list:
                logger.info("Doc list refresh: 0:%s added"
                            % doc.docid)
                self.__insert_doc(0, doc)
                must_rethumbnail.add(doc)
                docs.remove(doc)

        sentence = unicode(self.search_field.get_text(), encoding='utf-8')
        logger.info("Search: %s" % (sentence.encode('utf-8', 'replace')))

        # When a scan is done, we try to refresh only the current document.
        # However, the current document may be "New document". In which case
        # it won't appear as "New document" anymore. So we have to add a new
        # one to the list
        if sentence == u"":
            self.insert_new_doc()
            logger.debug("Doc list refresh: 'new doc' reinserted in the list")

        # Update the model of the remaining target docs
        doc_list = self.lists['doclist']
        doc_list = {doc_list[x]: x for x in xrange(0, len(doc_list))}
        for doc in set(docs):
            assert(doc in doc_list)
            doc_idx = doc_list[doc]
            logger.info("Doc list refresh: %d:%s refreshed"
                        % (doc_idx, doc.docid))
            doc_line = self.__get_doc_model_line(doc)
            if redo_thumbnails:
                must_rethumbnail.add(doc)
            else:
                # put back the previous thumbnail
                current_model = self.lists['matches']['model'][doc_idx]
                doc_line[1] = current_model[1]
            self.lists['matches'].set_model_line(doc_idx, doc_line)
            docs.remove(doc)

        assert(not docs)

        # reselect the active doc
        if self.doc is not None:
            if (self.doc.is_new
                    and len(self.lists['doclist']) > 0
                    and self.lists['doclist'][0].is_new):
                self.lists['matches'].select_idx(0)
            elif self.doc in doc_list:
                active_idx = doc_list[self.doc]
                self.lists['matches'].select_idx(active_idx)
            else:
                logger.warning("Selected document (%s) is not in the list"
                               % str(self.doc.docid))

        # and rethumbnail what must be
        if must_rethumbnail:
            docs = [x for x in must_rethumbnail]
            docs = [(doc_list[doc], doc) for doc in must_rethumbnail]
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

    def refresh_page_list(self):
        """
        Reload and refresh the page list.
        Warning: Will remove the thumbnails on all the pages
        """
        self.schedulers['main'].cancel_all(
            self.job_factories['page_thumbnailer']
        )

        model = [
            self.__get_page_model_line(page)
            for page in self.doc.pages
        ]
        self.lists['pages'].set_model(model)

        self.indicators['total_pages'].set_text(
            _("/ %d") % (self.doc.nb_pages))
        set_widget_state(self.doc_edit_widgets, self.doc.can_edit)
        set_widget_state(self.need_page_widgets, False)

        search = unicode(self.search_field.get_text(), encoding='utf-8')
        job = self.job_factories['page_thumbnailer'].make(self.doc, search)
        self.schedulers['main'].schedule(job)

    def refresh_label_list(self):
        """
        Reload and refresh the label list
        """
        self.schedulers['main'].cancel_all(
            self.job_factories['label_predictor_on_open_doc'])

        self.lists['labels']['model'].clear()
        labels = self.doc.labels

        for label in self.docsearch.label_list:
            self.lists['labels']['model'].append([
                [label],
                (label in labels),
                label,
                True,  # enabled
                False,  # predicted (will be updated)
            ])
        set_widget_state(self.need_label_widgets, False)

        job = self.job_factories['label_predictor_on_open_doc'].make(self.doc)
        self.schedulers['main'].schedule(job)

    def refresh_boxes(self):
        search = unicode(self.search_field.get_text(), encoding='utf-8')
        for page in self.page_drawers:
            page.show_all_boxes = self.show_all_boxes
            page.reload_boxes(search)

    def __resize_page(self, drawer):
        factor = self.get_zoom_factor(drawer.max_size)
        drawer.set_size_ratio(factor)

    def __update_page_positions(self):
        position_h = 0
        canvas_width = self.img['canvas'].visible_size[0]
        for drawer in self.page_drawers:
            drawer_size = drawer.size
            drawer.position = (
                max(0, (canvas_width - drawer_size[0]) / 2),
                position_h
            )
            position_h += drawer_size[1] + self.PAGE_MARGIN

    def update_page_sizes(self):
        for page in self.page_drawers:
            self.__resize_page(page)
        self.__update_page_positions()

    def show_doc(self, doc, force_refresh=False):
        if (self.doc is not None and self.doc == doc and not force_refresh):
            logger.info("Doc is already shown")
            return
        logger.info("Showing document %s" % doc)
        self.doc = doc

        self.schedulers['main'].cancel_all(
            self.job_factories['page_img_loader']
        )
        self.schedulers['main'].cancel_all(
            self.job_factories['page_boxes_loader']
        )
        self.img['canvas'].remove_all_drawers()

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
            scan_drawers = {
                page_nb: drawer
                for (page_nb, drawer) in scan_drawers
            }

        search = unicode(self.search_field.get_text(), encoding='utf-8')

        for page in doc.pages:
            if page.page_nb in scan_drawers:
                drawer = scan_drawers[page.page_nb]
            else:
                drawer = PageDrawer((0, 0), page, factories, schedulers,
                                    show_all_boxes=self.show_all_boxes,
                                    sentence=search)
            self.page_drawers.append(drawer)
            self.img['canvas'].add_drawer(drawer)

        if self.doc.docid in self.scan_drawers:
            for (page_nb, drawer) in self.scan_drawers[self.doc.docid]:
                if page_nb >= 0:
                    continue
                self.page_drawers.append(drawer)
                self.img['canvas'].add_drawer(drawer)

        self.update_page_sizes()
        self.img['canvas'].recompute_size()
        self.img['canvas'].upd_adjustments()

        is_new = doc.is_new
        can_edit = doc.can_edit

        set_widget_state(self.need_doc_widgets, True)
        set_widget_state(self.doc_edit_widgets, True)
        set_widget_state(self.need_doc_widgets, False,
                         cond=lambda widget: is_new)
        set_widget_state(self.doc_edit_widgets, False,
                         cond=lambda widget: not can_edit)

        if doc.nb_pages > 0:
            page = doc.pages[0]
        else:
            page = DummyPage(self.doc)
        self.show_page(page)

        pages_gui = self.lists['pages']['gui']
        if doc.can_edit:
            pages_gui.enable_model_drag_source(0, [], Gdk.DragAction.MOVE)
            pages_gui.drag_source_add_text_targets()
        else:
            pages_gui.unset_model_drag_source()
        self.refresh_page_list()
        self.refresh_label_list()

    def __select_page(self, page):
        self.page = page

        set_widget_state(self.need_page_widgets, True)
        set_widget_state(self.doc_edit_widgets, self.doc.can_edit)

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

    def show_page(self, page, force_refresh=False):
        if page is None:
            return

        if (page.doc != self.doc or force_refresh):
            self.show_doc(page.doc, force_refresh)

        logging.info("Showing page %s" % page)

        drawer = None
        for d in self.page_drawers:
            if d.page == page:
                drawer = d
                break

        if drawer is not None:
            self.img['canvas'].get_vadjustment().set_value(drawer.position[1])

        self.__select_page(page)

        if self.export['exporter'] is not None:
            logging.info("Canceling export")
            self.actions['cancel_export'][1].do()

        self.export['dialog'].set_visible(False)

        self.img['canvas'].redraw()

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
        self.img['canvas'].add_drawer(drawer)

        self.export['estimated_size'].set_text(sizeof_fmt(img_size))

    def __get_img_area_width(self):
        return self.img['viewport']['widget'].get_allocation().width

    def __get_img_area_height(self):
        return self.img['viewport']['widget'].get_allocation().height

    def get_raw_zoom_level(self):
        el_idx = self.lists['zoom_levels']['gui'].get_active()
        el_iter = self.lists['zoom_levels']['model'].get_iter(el_idx)
        return self.lists['zoom_levels']['model'].get_value(el_iter, 1)

    def get_zoom_factor(self, img_size):
        factor = self.get_raw_zoom_level()
        # factor is a postive float if user defined, 0 for full width and
        # -1 for full page
        if factor > 0.0:
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
        self.schedulers['main'].cancel_all(
            self.job_factories['export_previewer']
        )
        job = self.job_factories['export_previewer'].make(
            self.export['exporter'])
        self.schedulers['main'].schedule(job)

    def __on_img_resize_cb(self, viewport, rectangle):
        if self.export['exporter'] is not None:
            return

        old_size = self.img['viewport']['size']
        new_size = (rectangle.width, rectangle.height)
        if old_size == new_size:
            return

        logger.info("Image view port resized. (%d, %d) --> (%d, %d)"
                    % (old_size[0], old_size[1], new_size[0], new_size[1]))
        self.img['viewport']['size'] = new_size

        el_idx = self.lists['zoom_levels']['gui'].get_active()
        el_iter = self.lists['zoom_levels']['model'].get_iter(el_idx)
        factor = self.lists['zoom_levels']['model'].get_value(el_iter, 1)
        if factor > 0.0:
            return

        for page in self.page_drawers:
            self.__resize_page(page)
        self.__update_page_positions()
        self.show_page(self.page)

    def on_page_editing_img_edit_start_cb(self, job, page):
        self.set_mouse_cursor("Busy")
        self.set_progression(job, 0.0, _("Updating the image ..."))

    def on_page_editing_done_cb(self, job, page):
        self.set_progression(job, 0.0, "")
        self.set_mouse_cursor("Normal")
        if self.page:
            self.page.drop_cache()
        if self.doc:
            self.doc.drop_cache()
        if page.page_nb == 0:
            self.refresh_doc_list()
        self.refresh_page_list()
        self.show_page(page)

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
        GLib.idle_add(self.refresh_page_list)
        doc = obj.doc
        GLib.idle_add(self.refresh_docs, {doc})

    def __on_match_list_drag_data_received_cb(self, widget, drag_context, x, y,
                                              selection_data, info, time):
        obj_id = selection_data.get_text()
        target = self.lists['matches']['gui'].get_dest_item_at_pos(x, y)
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
        target_doc = self.lists['matches']['model'][target][2]
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
        GLib.idle_add(self.refresh_page_list)

        # the index update will start a doc list refresh when finished
        job = self.job_factories['index_updater'].make(
            docsearch=self.docsearch,
            new_docs=set(),
            upd_docs=upd_docs,
            del_docs=del_docs,
            optimize=False,
            reload_all=False,
            reload_thumbnails=True
        )
        self.schedulers['main'].schedule(job)

    def __on_doc_lines_shown(self, docs):
        job = self.job_factories['doc_thumbnailer'].make(docs)
        self.schedulers['main'].schedule(job)

    def __on_window_resized_cb(self, _, rectangle):
        (w, h) = (rectangle.width, rectangle.height)
        self.__config['main_win_size'].value = (w, h)

    def get_doc_sorting(self):
        for (widget, sort_func, sorting_name) in self.sortings:
            if widget.get_active():
                return (sorting_name, sort_func)
        return (self.sortings[0][0], self.sortings[0][1])

    def __get_show_all_boxes(self):
        return self.__show_all_boxes

    def __set_show_all_boxes(self, value):
        LABELS = {
            False: _("Highlight all the words"),
            True: _("Unhighlight the words"),
        }

        self.__advanced_menu.remove(0)
        self.__show_all_boxes_widget.set_label(LABELS[value])
        self.__advanced_menu.insert_item(0, self.__show_all_boxes_widget)

        self.__show_all_boxes = value

    show_all_boxes = property(__get_show_all_boxes, __set_show_all_boxes)

    def __on_img_window_moved(self):
        pos = self.img['canvas'].position
        size = self.img['canvas'].visible_size
        pos = (pos[0] + (size[0] / 2),
               pos[1] + (size[1] / 2))
        drawer = self.img['canvas'].get_drawer_at(pos)
        if drawer is None:
            return
        page = drawer.page
        if page is None:
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
            for (page_nb, drawer) in drawers[:]:
                if (scan_workflow == drawer
                        or scan_workflow == drawer.scan_workflow):
                    drawers.remove((page_nb, drawer))
                    return docid
        raise ValueError("ScanWorkflow not found")

    def add_scan_workflow(self, doc, scan_workflow_drawer, page_nb=-1):
        if doc.docid not in self.scan_drawers:
            self.scan_drawers[doc.docid] = []
        self.scan_drawers[doc.docid].append((page_nb, scan_workflow_drawer))

        if self.doc.docid == doc.docid:
            self.page = None
            self.show_doc(self.doc, force_refresh=True)
            self.img['canvas'].add_drawer(scan_workflow_drawer)
            self.img['canvas'].recompute_size()
            self.img['canvas'].get_vadjustment().set_value(
                scan_workflow_drawer.position[1])

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
        self.refresh_page_list()

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
        if new:
            job = self.job_factories['index_updater'].make(
                self.docsearch, new_docs={doc}, optimize=False,
                reload_all=False, reload_thumbnails=True)
        else:
            job = self.job_factories['index_updater'].make(
                self.docsearch, upd_docs={doc}, optimize=False,
                reload_all=False, reload_thumbnails=True)
        job.connect("index-update-end", lambda job:
                    GLib.idle_add(self.refresh_doc_list))
        self.schedulers['main'].schedule(job)
