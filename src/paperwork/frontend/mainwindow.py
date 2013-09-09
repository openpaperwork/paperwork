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

import PIL.Image
import gettext
import logging
import cairo
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GdkPixbuf

import pyinsane.abstract_th as pyinsane

from paperwork.frontend.aboutdialog import AboutDialog
from paperwork.frontend.actions import SimpleAction
from paperwork.frontend.doceditdialog import DocEditDialog
from paperwork.frontend.jobs import Job, JobFactory, JobScheduler, JobFactoryProgressUpdater
from paperwork.frontend.label_editor import LabelEditor
from paperwork.frontend.multiscan import MultiscanDialog
from paperwork.frontend.page_edit import PageEditingDialog
from paperwork.frontend.settingswindow import SettingsWindow
from paperwork.backend import docimport
from paperwork.backend.common.page import DummyPage
from paperwork.backend.docsearch import DocSearch
from paperwork.backend.docsearch import DummyDocSearch
from paperwork.backend.img.doc import ImgDoc
from paperwork.backend.img.page import ImgPage
from paperwork.util import add_img_border
from paperwork.util import ask_confirmation
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile
from paperwork.util import maximize_scan_area
from paperwork.util import popup_no_scanner_found
from paperwork.util import set_scanner_opt
from paperwork.util import sizeof_fmt

_ = gettext.gettext
logger = logging.getLogger(__name__)


def check_scanner(main_win, config):
    if config.scanner_devid is not None:
        return True
    main_win.actions['open_settings'][1].do()
    return False


def sort_documents_by_date(documents):
    documents.sort()
    documents.reverse()


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
        elif step == DocSearch.INDEX_STEP_CLEANING:
            txt = _('Cleaning ...')
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
            docsearch = DocSearch(self.__config.workdir, self.__progress_cb)
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
                    lambda job: GObject.idle_add(
                        self.__main_window.on_index_loading_start_cb, job))
        job.connect('index-loading-progression',
                    lambda job, progression, txt:
                    GObject.idle_add(self.__main_window.set_progression,
                                     job, progression, txt))
        job.connect('index-loading-end',
                    lambda loader, docsearch: GObject.idle_add(
                        self.__main_window.on_index_loading_end_cb, loader,
                        docsearch))
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
            lambda job: GObject.idle_add(
                self.__main_win.on_doc_examination_start_cb, job))
        job.connect(
            'doc-examination-progression',
            lambda job, progression, txt: GObject.idle_add(
                self.__main_win.set_progression, job, progression, txt))
        job.connect(
            'doc-examination-end',
            lambda job: GObject.idle_add(
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
                new_docs=[], upd_docs=[], del_docs=[],
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
        self.total = len(self.new_docs) + len(self.upd_docs) + len(self.del_docs)
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
        GObject.idle_add(self.__wakeup)
        self.__condition.wait()
        self.__condition.release()

    def do(self):
        # keep in mind that we may have been interrupted and then called back
        # later

        self.can_run = True

        total = len(self.new_docs) + len(self.upd_docs) + len(self.del_docs)
        if total <= 0 and self.index_updater is None:
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
                         GObject.idle_add(self.index_updater.cancel))


GObject.type_register(JobIndexUpdater)


class JobFactoryIndexUpdater(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "IndexUpdater")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch,
            new_docs, upd_docs, del_docs, optimize=True):
        job = JobIndexUpdater(self, next(self.id_generator), self.__config,
                              docsearch, new_docs, upd_docs, del_docs, optimize)
        job.connect('index-update-start',
                    lambda updater:
                    GObject.idle_add(self.__main_win.on_index_update_start_cb,
                                     updater))
        job.connect('index-update-progression',
                    lambda updater, progression, txt:
                    GObject.idle_add(self.__main_win.set_progression, updater,
                                     progression, txt))
        job.connect('index-update-write',
                    lambda updater:
                    GObject.idle_add(self.__main_win.on_index_update_write_cb,
                                     updater))
        job.connect('index-update-end',
                    lambda updater:
                    GObject.idle_add(self.__main_win.on_index_update_end_cb,
                                     updater))
        return job


class JobDocSearcher(Job):
    """
    Search the documents
    """

    __gsignals__ = {
        'search-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        # first obj: array of documents
        # second obj: array of suggestions
        'search-result': (GObject.SignalFlags.RUN_LAST, None,
                          (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT)),
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

        documents = self.__docsearch.find_documents(self.search)
        if not self.can_run:
            return

        if self.search == u"":
            # when no specific search has been done, the sorting is always
            # the same
            sort_documents_by_date(documents)
            # append a new document to the list
            documents.insert(0, ImgDoc(self.__config.workdir))
        else:
            self.__sort_func(documents)
        if not self.can_run:
            return

        suggestions = self.__docsearch.find_suggestions(self.search)
        if not self.can_run:
            return

        self.emit('search-result', documents, suggestions)

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
        job.connect('search-result',
            lambda searcher, documents, suggestions:
            GObject.idle_add(self.__main_win.on_search_result_cb,
                             documents, suggestions))
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

        for page_idx in range(self.__current_idx, nb_pages):
            page = pages[page_idx]
            img = page.get_thumbnail(JobDocThumbnailer.THUMB_WIDTH)
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
                    GObject.idle_add(self.__main_win.on_page_thumbnailing_start_cb,
                                     thumbnailer))
        job.connect('page-thumbnailing-page-done',
                    lambda thumbnailer, page_idx, thumbnail:
                    GObject.idle_add(self.__main_win.on_page_thumbnailing_page_done_cb,
                                     thumbnailer, page_idx, thumbnail))
        job.connect('page-thumbnailing-end',
                    lambda thumbnailer:
                    GObject.idle_add(self.__main_win.on_page_thumbnailing_end_cb,
                                     thumbnailer))
        return job


class JobDocThumbnailer(Job):
    """
    Generate doc list thumbnails
    """

    THUMB_WIDTH = 150
    THUMB_HEIGHT = 220
    THUMB_BORDER = 1

    __gsignals__ = {
        'doc-thumbnailing-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'doc-thumbnailing-doc-done': (GObject.SignalFlags.RUN_LAST, None,
                                      (GObject.TYPE_INT, # doc idx in the list
                                       GObject.TYPE_PYOBJECT,
                                       GObject.TYPE_INT, # current doc
                                       # number of docs being thumbnailed
                                       GObject.TYPE_INT,
                                      )),
        'doc-thumbnailing-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = True
    priority = 20

    def __init__(self, factory, id, doclist):
        Job.__init__(self, factory, id)
        self.__doclist = doclist
        self.__current_idx = -1

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

            img = doc.pages[0].get_thumbnail(self.THUMB_WIDTH)
            if not self.can_run:
                return

            (width, height) = img.size
            # always make sure the thumbnail has a specific height
            # otherwise the scrollbar keep moving while loading
            if height > self.THUMB_HEIGHT:
                img = img.crop((0, 0, width, self.THUMB_HEIGHT))
                img = img.copy()
            else:
                new_img = PIL.Image.new('RGBA', (width, self.THUMB_HEIGHT),
                                        '#FFFFFF')
                h = (self.THUMB_HEIGHT - height) / 2
                new_img.paste(img, (0, h, width, h+height))
                img = new_img
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
            doclist --- must be an array of (position, document), position being
            the position of the document
        """
        job = JobDocThumbnailer(self, next(self.id_generator), doclist)
        job.connect(
            'doc-thumbnailing-start',
            lambda thumbnailer:
            GObject.idle_add(self.__main_win.on_doc_thumbnailing_start_cb,
                             thumbnailer))
        job.connect(
            'doc-thumbnailing-doc-done',
            lambda thumbnailer, doc_idx, thumbnail, doc_nb, total_docs:
            GObject.idle_add(self.__main_win.on_doc_thumbnailing_doc_done_cb,
                             thumbnailer, doc_idx, thumbnail, doc_nb,
                             total_docs))
        job.connect(
            'doc-thumbnailing-end',
            lambda thumbnailer:
            GObject.idle_add(self.__main_win.on_doc_thumbnailing_end_cb,
                             thumbnailer))
        return job


class JobImgBuilder(Job):
    """
    Resize and paint on the page
    """
    __gsignals__ = {
        'img-building-start': (GObject.SignalFlags.RUN_LAST, None,
                               (GObject.TYPE_BOOLEAN,  # True == warn the user
                               )),
        'img-building-canceled': (GObject.SignalFlags.RUN_LAST, None,
                                  (GObject.TYPE_BOOLEAN,  # True == warned the user
                                  )),
        'img-building-result-pixbuf': (GObject.SignalFlags.RUN_LAST, None,
                                       (GObject.TYPE_BOOLEAN,  # True == warned the user
                                        GObject.TYPE_FLOAT, GObject.TYPE_INT,
                                        GObject.TYPE_PYOBJECT,  # pixbuf
                                        # array of boxes
                                        GObject.TYPE_PYOBJECT,
                                       )),
        'img-building-result-clear': (GObject.SignalFlags.RUN_LAST, None,
                                      (GObject.TYPE_BOOLEAN,  # True == warned the user
                                      )),
        'img-building-result-stock': (GObject.SignalFlags.RUN_LAST, None,
                                      (GObject.TYPE_BOOLEAN,  # True == warned the user
                                       GObject.TYPE_STRING, )),
    }

    can_stop = True
    priority = 450

    def __init__(self, factory, id, page, zoom_factor_func, warn_user):
        Job.__init__(self, factory, id)
        self.__page = page
        self.__zoom_factor_func = zoom_factor_func
        self.__started_once = False
        self.done = False
        self.warn_user = warn_user

    def do(self):
        if self.done:
            return
        self.can_run = True

        try:
            if (not self.__started_once and self.warn_user):
                # warn_user == True is the normal mode where we change the
                # GUI to show the user we have taken its request into account
                # and we are loading the new image
                # warn_user == False is a sneaky mode where we don't warn
                # them
                self.emit('img-building-start', self.warn_user)
                self.__started_once = True

            if not self.can_run:
                return

            img = self.__page.img  # load the image
            if img is None:
                self.emit('img-building-result-clear', self.warn_user)
                self.done = True
                return
            if not self.can_run:
                return

            pixbuf = image2pixbuf(img)
            if not self.can_run:
                return

            original_width = pixbuf.get_width()

            factor = self.__zoom_factor_func(original_width)
            logger.info("Zoom: %f" % (factor))

            wanted_width = int(factor * pixbuf.get_width())
            wanted_height = int(factor * pixbuf.get_height())
            pixbuf = pixbuf.scale_simple(wanted_width, wanted_height,
                                         GdkPixbuf.InterpType.BILINEAR)
            if not self.can_run:
                return
            self.emit('img-building-result-pixbuf', self.warn_user, factor,
                      original_width, pixbuf, self.__page.boxes)
            self.done = True
        except Exception:
            self.emit('img-building-result-stock', self.warn_user,
                      Gtk.STOCK_DIALOG_ERROR)
            self.done = True
            raise

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()
        if not will_resume and not self.done:
            self.emit('img-building-canceled', self.warn_user)
            self.done = True


GObject.type_register(JobImgBuilder)


class JobFactoryImgBuilder(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "ImgBuilder")
        self.__main_win = main_win

    def make(self, page, warn_user=True):
        job = JobImgBuilder(self, next(self.id_generator), page,
                            self.__main_win.get_zoom_factor,
                            warn_user)
        job.connect('img-building-start',
                    lambda builder, warn_user:
                    GObject.idle_add(self.__main_win.on_img_building_start,
                                     warn_user))
        job.connect('img-building-canceled',
                    lambda builder, warned_user:
                    GObject.idle_add(self.__main_win.on_img_building_canceled,
                                     warned_user))
        job.connect('img-building-result-pixbuf',
                    lambda builder, warned_user, factor, original_width, img, boxes:
                    GObject.idle_add(self.__main_win.on_img_building_result_pixbuf,
                                     builder, warn_user,
                                     factor, original_width, img, boxes))
        job.connect('img-building-result-stock',
                    lambda builder, warned_user, img:
                    GObject.idle_add(self.__main_win.on_img_building_result_stock,
                                     warn_user, img))
        job.connect('img-building-result-clear',
                    lambda builder, warned_user:
                    GObject.idle_add(self.__main_win.on_img_building_result_clear,
                                     warned_user))
        return job


class JobBoxesRefresher(Job):
    __gsignals__ = {
        'highlighted-boxes': (GObject.SignalFlags.RUN_LAST, None,
                              (
                                  # highlighted boxes
                                  GObject.TYPE_PYOBJECT,
                              )),
    }

    can_stop = True
    priority = 30

    def __init__(self, factory, id, page, search):
        Job.__init__(self, factory, id)
        self.__page = page
        self.__search = search

    def do(self):
        self.can_run = True
        if not self.can_run:
            return

        highlighted = self.__page.get_boxes(self.__search)
        if not self.can_run:
            return

        self.emit('highlighted-boxes', highlighted)

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobBoxesRefresher)


class JobFactoryBoxesRefresher(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "BoxesRefresher")
        self.__main_win = main_win

    def make(self, page, search):
        job = JobBoxesRefresher(self, next(self.id_generator), page, search)
        job.connect('highlighted-boxes',
                    lambda job, boxes:
                    GObject.idle_add(self.__main_win.on_highlighted_boxes,
                                     boxes))
        return job


class JobBoxesSelecter(Job):
    __gsignals__ = {
        'selected-boxes': (GObject.SignalFlags.RUN_LAST, None,
                           (
                               # selected boxes
                               GObject.TYPE_PYOBJECT,
                           )),
    }

    can_stop = True
    priority = 30

    def __init__(self, factory, id, boxes, mouse_position, get_box_pos_func):
        Job.__init__(self, factory, id)
        self.__boxes = boxes
        self.__mouse_pos = mouse_position
        self.__get_box_pos_func = get_box_pos_func

    def do(self):
        self.can_run = True
        self._wait(0.5)
        if not self.can_run:
            return

        mouse_x, mouse_y = self.__mouse_pos
        selected = set()

        for line in self.__boxes:
            if not self.can_run:
                return

            pos = self.__get_box_pos_func(line)
            ((a, b), (c, d)) = pos
            if (mouse_x < a or mouse_y < b
                    or mouse_x > c or mouse_y > d):
                continue

            for box in line.word_boxes:
                if not self.can_run:
                    return

                pos = self.__get_box_pos_func(box)
                ((a, b), (c, d)) = pos
                if (mouse_x < a or mouse_y < b
                        or mouse_x > c or mouse_y > d):
                    continue
                selected.add(box)

        self.emit('selected-boxes', selected)

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobBoxesSelecter)


class JobFactoryBoxesSelecter(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "BoxesSelecter")
        self.__main_win = main_win

    def make(self, boxes, mouse_position, get_box_pos_func):
        job = JobBoxesSelecter(self, next(self.id_generator),
                               boxes, mouse_position, get_box_pos_func)
        job.connect('selected-boxes',
                    lambda job, boxes:
                    GObject.idle_add(self.__main_win.on_selected_boxes,
                                     boxes))
        return job


class JobFactoryBoxesRefresher(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "BoxesRefresher")
        self.__main_win = main_win

    def make(self, page, search):
        job = JobBoxesRefresher(self, next(self.id_generator), page, search)
        job.connect('highlighted-boxes',
                    lambda job, boxes:
                    GObject.idle_add(self.__main_win.on_highlighted_boxes,
                                     boxes))
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
                    GObject.idle_add(
                        self.__main_win.on_label_updating_start_cb,
                        updater))
        job.connect('label-updating-doc-updated',
                    lambda updater, progression, doc_name:
                    GObject.idle_add(
                        self.__main_win.on_label_updating_doc_updated_cb,
                        updater, progression, doc_name))
        job.connect('label-updating-end',
                    lambda updater:
                    GObject.idle_add(
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
                    GObject.idle_add(self.__main_win.on_label_updating_start_cb,
                                     deleter))
        job.connect('label-deletion-doc-updated',
                    lambda deleter, progression, doc_name:
                    GObject.idle_add(
                        self.__main_win.on_label_deletion_doc_updated_cb,
                        deleter, progression, doc_name))
        job.connect('label-deletion-end',
                    lambda deleter:
                    GObject.idle_add(self.__main_win.on_label_updating_end_cb,
                                     deleter))
        return job


class JobOCRRedoer(Job):
    __gsignals__ = {
        'redo-ocr-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'redo-ocr-doc-updated': (GObject.SignalFlags.RUN_LAST, None,
                                 (GObject.TYPE_FLOAT, GObject.TYPE_STRING)),
        'redo-ocr-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    # we make it non-interruptible because there is no way for us to start
    # back from where we stopped, and redoing all the docs may take far too
    # much time
    # TODO(Jflesch): Make it interruptible (use iter(target))
    can_stop = False
    priority = 5

    def __init__(self, factory, id, langs, target):
        Job.__init__(self, factory, id)
        self.__target = target
        self.__langs = langs

    def __progress_cb(self, progression, total, step, doc):
        logger.info("OCR progression: %s : %d / %d : %s"
                    % (step, progression, total, doc.name))
        self.emit('redo-ocr-doc-updated', float(progression) / (total + 1),
                  doc.name)

    def do(self):
        self.emit('redo-ocr-start')
        try:
            self.__target.redo_ocr(self.__langs, self.__progress_cb)
        finally:
            self.emit('redo-ocr-end')


GObject.type_register(JobOCRRedoer)


class JobFactoryOCRRedoer(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "OCRRedoer")
        self.__main_win = main_win
        self.__config = config

    def make(self, target):
        job = JobOCRRedoer(self, next(self.id_generator), self.__config.langs,
                           target)
        job.connect('redo-ocr-start',
                    lambda ocr_redoer:
                    GObject.idle_add(self.__main_win.on_redo_ocr_start_cb,
                                     ocr_redoer))
        job.connect('redo-ocr-doc-updated',
                    lambda ocr_redoer, progression, doc_name:
                    GObject.idle_add(
                        self.__main_win.on_redo_ocr_doc_updated_cb,
                        ocr_redoer, progression, doc_name))
        job.connect('redo-ocr-end',
                    lambda ocr_redoer:
                    GObject.idle_add(self.__main_win.on_redo_ocr_end_cb,
                                     ocr_redoer))
        return job


class JobSingleScan(Job):
    __gsignals__ = {
        'single-scan-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'single-scan-ocr': (GObject.SignalFlags.RUN_LAST, None, ()),
        'single-scan-done': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_PYOBJECT,)),  # ImgPage
        'single-scan-no-scanner-found': (GObject.SignalFlags.RUN_LAST, None,
                                         ()),
        'single-scan-error': (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_STRING,)),
    }

    can_stop = False
    priority = 5

    def __init__(self, factory, id, config, docsearch, target_doc):
        Job.__init__(self, factory, id)
        self.__config = config
        self.doc = target_doc
        self.__docsearch = docsearch
        self.__ocr_running = False
        self.done = False

    def __scan_progress_cb(self, progression, total, step, doc=None):
        if (step == ImgPage.SCAN_STEP_OCR) and (not self.__ocr_running):
            self.emit('single-scan-ocr')
            self.__ocr_running = True

    def do(self):
        self.emit('single-scan-start')

        try:
            self.__ocr_running = False
            try:
                scanner = self.__config.get_scanner_inst()
                try:
                    # any source is actually fine. we just have a clearly defined
                    # preferred order
                    set_scanner_opt('source', scanner.options['source'],
                                    ["Auto", "FlatBed",
                                     ".*ADF.*", ".*Feeder.*"])
                except (KeyError, pyinsane.SaneException), exc:
                    logger.error("Warning: Unable to set scanner source: "
                                 "%s" % exc)
                maximize_scan_area(scanner)
                scan_src = scanner.scan(multiple=False)
            except pyinsane.SaneException, exc:
                logger.error("No scanner found !")
                self.emit('single-scan-no-scanner-found')
                raise
            try:
                resolution = scanner.options['resolution'].value
            except pyinsane.SaneException, exc:
                resolution = self.__config.scanner_resolution
                logger.warning("Failed to read the resolution set on"
                               " the scanner: %s. Assuming %d"
                               % (str(exc), resolution))
            self.doc.scan_single_page(scan_src, resolution,
                                      self.__config.scanner_calibration,
                                      self.__config.langs,
                                      self.__scan_progress_cb)
            page = self.doc.pages[self.doc.nb_pages - 1]
            self.__docsearch.index_page(page)
            self.emit('single-scan-done', page)
        except Exception, exc:
            self.emit('single-scan-error', str(exc))
            raise


GObject.type_register(JobSingleScan)


class JobFactorySingleScan(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "SingleScan")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch, target_doc):
        job = JobSingleScan(self, next(self.id_generator), self.__config,
                            docsearch, target_doc)
        job.connect('single-scan-start',
                    lambda job:
                    GObject.idle_add(self.__main_win.on_single_scan_start,
                                     job))
        job.connect('single-scan-ocr',
                    lambda job:
                    GObject.idle_add(self.__main_win.on_single_scan_ocr,
                                     job))
        job.connect('single-scan-done',
                    lambda job, page:
                    GObject.idle_add(self.__main_win.on_single_scan_done,
                                     job, page))
        job.connect('single-scan-no-scanner-found',
                    lambda job:
                    GObject.idle_add(popup_no_scanner_found,
                                     self.__main_win.window))
        job.connect('single-scan-error',
                    lambda job, error:
                    GObject.idle_add(self.__main_win.on_single_scan_error,
                                     job, error))
        return job


class JobImporter(Job):
    __gsignals__ = {
        'import-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'import-done': (GObject.SignalFlags.RUN_LAST, None,
                        (GObject.TYPE_PYOBJECT,  # Doc
                         GObject.TYPE_PYOBJECT),),  # Page
    }

    can_stop = False
    priority = 10

    def __init__(self, factory, id,
                 config, docsearch, doc,
                 importer, file_uri):
        Job.__init__(self, factory, id)
        self.__config = config
        self.__docsearch = docsearch
        self.__doc = doc
        self.__importer = importer
        self.__file_uri = file_uri

    def do(self):
        self.emit('import-start')
        (doc, page) = self.__importer.import_doc(
            self.__file_uri, self.__config, self.__docsearch, self.__doc)
        self.emit('import-done', doc, page)


GObject.type_register(JobImporter)


class JobFactoryImporter(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "Importer")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch, doc, importer, file_uri):
        job = JobImporter(self, next(self.id_generator),
                          self.__config, docsearch, doc,
                          importer, file_uri)
        job.connect('import-start',
                    lambda job:
                    GObject.idle_add(self.__main_win.on_import_start, job))
        job.connect('import-done',
                    lambda job, doc, page:
                    GObject.idle_add(self.__main_win.on_import_done, job, doc, page))
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

        pixbuf = image2pixbuf(img)
        if not self.can_run:
            return

        self.emit('export-preview-done', size, pixbuf)

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
                    GObject.idle_add(self.__main_win.on_export_preview_start))
        job.connect('export-preview-done',
                    lambda job, size, pixbuf:
                    GObject.idle_add(self.__main_win.on_export_preview_done,
                                     size, pixbuf))
        return job


class JobPageEditor(Job):
    __gsignals__ = {
        'page-editing-img-edit': (GObject.SignalFlags.RUN_LAST, None,
                                  (GObject.TYPE_PYOBJECT, )),
        'page-editing-ocr': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_PYOBJECT, )),
        'page-editing-index-upd': (GObject.SignalFlags.RUN_LAST, None,
                                   (GObject.TYPE_PYOBJECT, )),
        'page-editing-done': (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_PYOBJECT, )),
    }

    can_stop = False
    priority = 10

    def __init__(self, factory, id, docsearch, langs, page, changes=[]):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__langs = langs
        self.__page = page
        self.__changes = changes[:]

    def do(self):
        self.emit('page-editing-img-edit', self.__page)
        try:
            img = self.__page.img
            for change in self.__changes:
                img = change.do(img, 1.0)
            self.__page.img = img

            if self.__langs is not None:
                self.emit('page-editing-ocr', self.__page)
                self.__page.redo_ocr(self.__langs)

                self.emit('page-editing-index-upd', self.__page)
                index_upd = self.__docsearch.get_index_updater(optimize=False)
                index_upd.upd_doc(self.__page.doc)
                index_upd.commit()
        finally:
            self.emit('page-editing-done', self.__page)


GObject.type_register(JobPageEditor)


class JobFactoryPageEditor(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "PageEditor")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch, page, changes):
        job = JobPageEditor(self, next(self.id_generator), docsearch,
                            self.__config.langs, page, changes)
        job.connect('page-editing-img-edit',
                    lambda job, page:
                    GObject.idle_add(
                        self.__main_win.on_page_editing_img_edit_start_cb,
                        job, page))
        job.connect('page-editing-ocr',
                    lambda job, page:
                    GObject.idle_add(self.__main_win.on_page_editing_ocr_cb,
                                     job, page))
        job.connect('page-editing-index-upd',
                    lambda job, page:
                    GObject.idle_add(
                        self.__main_win.on_page_editing_index_upd_cb,
                        job, page))
        job.connect('page-editing-done',
                    lambda job, page:
                    GObject.idle_add(self.__main_win.on_page_editing_done_cb,
                                     job, page))
        return job


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

        match_list = self.__main_win.lists['matches']['gui']
        selection_path = match_list.get_selected_items()
        if len(selection_path) <= 0:
            logger.info("No document selected. Can't open")
            return
        doc_idx = selection_path[0].get_indices()[0]
        doc = self.__main_win.lists['matches']['model'][doc_idx][2]

        logger.info("Showing doc %s" % doc)
        self.__main_win.show_doc(doc_idx, doc)


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
            search = unicode(self.__main_win.search_field.get_text(), encoding='utf-8')
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


class ActionRebuildPage(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Reload current page")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.schedulers['main'].cancel_all(
            self.__main_win.job_factories['img_builder'])
        job = self.__main_win.job_factories['img_builder'].make(
            self.__main_win.page)
        self.__main_win.schedulers['main'].schedule(job)


class ActionRefreshBoxes(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Refresh current page boxes")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_boxes()


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
            logger.info("Action: Adding label '%s' on document '%s'"
                   % (label.name, str(self.__main_win.doc)))
            self.__main_win.docsearch.add_label(self.__main_win.doc, label)
        else:
            logger.info("Action: Removing label '%s' on document '%s'"
                   % (label.name, self.__main_win.doc))
            self.__main_win.docsearch.remove_label(self.__main_win.doc, label)
        self.__main_win.refresh_label_list()
        self.__main_win.refresh_docs({self.__main_win.doc},
                                     redo_thumbnails=False)

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
            self.__main_win.docsearch.add_label(self.__main_win.doc,
                                                labeleditor.label)
        self.__main_win.refresh_label_list()
        self.__main_win.refresh_docs({self.__main_win.doc},
                                     redo_thumbnails=False)


class ActionEditLabel(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Editing label")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        label_list = self.__main_win.lists['labels']['gui']
        selection_path = label_list.get_selection().get_selected()
        if selection_path[1] is None:
            logger.warn("No label selected")
            return True
        label = selection_path[0].get_value(selection_path[1], 2)

        new_label = copy(label)
        editor = LabelEditor(new_label)
        if not editor.edit(self.__main_win.window):
            logger.warn("Label edition cancelled")
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
            logger.warn("No label selected")
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
        os.system('xdg-open "%s"' % (self.__main_win.doc.path))


class ActionPrintDoc(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open print dialog")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        print_settings = Gtk.PrintSettings()
        print_op = Gtk.PrintOperation()
        print_op.set_print_settings(print_settings)
        print_op.set_n_pages(self.__main_win.doc.nb_pages)
        print_op.set_current_page(self.__main_win.page.page_nb)
        print_op.set_use_full_page(False)
        print_op.set_job_name(str(self.__main_win.doc))
        print_op.set_export_filename(str(self.__main_win.doc) + ".pdf")
        print_op.set_allow_async(True)
        print_op.connect("draw-page", self.__main_win.doc.print_page_cb)
        print_op.set_embed_page_setup(True)
        print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG,
                     self.__main_win.window)


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

    def do(self):
        SimpleAction.do(self)
        if not check_scanner(self.__main_win, self.__config):
            return
        doc = self.__main_win.doc

        self.__main_win.schedulers['main'].cancel_all(
            self.__main_win.job_factories['single_scan'])
        job = self.__main_win.job_factories['single_scan'].make(
            self.__main_win.docsearch, doc)
        self.__main_win.schedulers['main'].schedule(job)


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
                   GObject.idle_add(self.__show_page, page))

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
        widget_tree = load_uifile("import.glade")
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

        file_uri = self.__select_file()
        if file_uri is None:
            return

        importers = docimport.get_possible_importers(file_uri,
                                                     self.__main_win.doc)
        if len(importers) <= 0:
            msg = (_("Don't know how to import '%s'. Sorry.") %
                   (os.path.basename(file_uri)))
            flags = (Gtk.DialogFlags.MODAL
                     | Gtk.DialogFlags.DESTROY_WITH_PARENT)
            dialog = Gtk.MessageDialog(parent=self.__main_win.window,
                                       flags=flags,
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

        job = self.__main_win.job_factories['importer'].make(
            self.__main_win.docsearch, self.__main_win.doc,
            importer, file_uri)
        self.__main_win.schedulers['main'].schedule(job)


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

        logger.info("Deleting ...")
        doc.destroy()
        index_upd = self.__main_win.docsearch.get_index_updater(
            optimize=False)
        index_upd.del_doc(docid)
        index_upd.commit()
        logger.info("Deleted")

        self.__main_win.actions['new_doc'][1].do()
        self.__main_win.refresh_docs({doc})


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
        logger.info("Deleting ...")
        self.__main_win.page.destroy()
        logger.info("Deleted")
        self.__main_win.page = None
        for widget in self.__main_win.need_page_widgets:
            widget.set_sensitive(False)
        self.__main_win.refresh_docs({self.__main_win.doc})
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

        doc = self.__main_win.doc
        job = self.__main_win.job_factories['ocr_redoer'].make(doc)
        self.__main_win.schedulers['main'].schedule(job)


class ActionRedoAllOCR(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Redoing doc ocr")
        self.__main_win = main_window

    def do(self):
        if not ask_confirmation(self.__main_win.window):
            return
        SimpleAction.do(self)

        self.__main_win.schedulers['main'].cancel_all(
            self.__main_win.job_factories['ocr_redoer'])
        job = self.__main_win.job_factories['ocr_redoer'].make(
            self.__main_win.docsearch)
        self.__main_win.schedulers['main'].schedule(job)


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
            for widget in widgets:
                widget.set_sensitive(sensitive)

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
            logger.warn("File path for export canceled")
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
            logger.info("%f <= %f < %f ?" % (zoom_list[zoom_list_idx][0],
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


class ActionEditDoc(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Edit doc")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        DocEditDialog(self.__main_win, self.__config, self.__main_win.doc)


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

        for scheduler in self.__main_win.schedulers.values():
            scheduler.stop()

        self.__config.write()
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
        job.connect('doc-examination-end', lambda job: GObject.idle_add(
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
            self.__main_win.docsearch, self.__main_win.page, changes=todo)
        self.__main_win.schedulers['main'].schedule(job)


class JobProgressiveList(Job):
    can_stop = True
    priority = 500

    def __init__(self, factory, id, progressive_list):
        Job.__init__(self, factory, id)
        self.__progressive_list = progressive_list
        self.can_run = True

    def do(self):
        self._wait(0.5)
        if not self.can_run:
            return
        GObject.idle_add(self.__progressive_list.display_extra)

    def stop(self, will_resume=True):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobProgressiveList)


class JobFactoryProgressiveList(JobFactory):
    def __init__(self, progressive_list):
        JobFactory.__init__(self, "Progressive List")
        self.progressive_list = progressive_list

    def make(self):
        return JobProgressiveList(self, next(self.id_generator),
                                  self.progressive_list)


class ProgressiveList(GObject.GObject):
    """
    We use GtkIconView to display documents and pages. However this widget
    doesn't like having too many elements to display: it keeps redrawing the
    list when the mouse goes over it --> with 600 documents, this may be
    quite long.

    So instead, we display only X elements. When the user scroll down,
    we add Y elements to the list, etc.
    """

    NB_EL_DISPLAYED_INITIALLY = 100
    NB_EL_DISPLAY_EXTRA_WHEN_LOWER_THAN = 0.85
    NB_EL_DISPLAYED_ADDITIONNAL = int((1.0 - NB_EL_DISPLAY_EXTRA_WHEN_LOWER_THAN)
                                      * NB_EL_DISPLAYED_INITIALLY)

    __gsignals__ = {
        'lines-shown': (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_PYOBJECT,) ),  # [(line_idx, obj), ... ]
    }

    def __init__(self, name,
                 main_win,
                 gui, scrollbars, model):
        GObject.GObject.__init__(self)
        self.name = name
        self.__main_win = main_win
        self.widget_gui = gui

        self.widget_scrollbars = scrollbars
        self._vadjustment = scrollbars.get_vadjustment()

        self.model = model
        self.model_content = []

        self.nb_displayed = 0

        self._vadjustment.connect(
            "value-changed",
            lambda widget: GObject.idle_add(self.__on_scrollbar_moved))

        self.job_factory = JobFactoryProgressiveList(self)

    def set_model(self, model_content):
        self.model_content = model_content

        self.widget_gui.freeze_child_notify()
        self.widget_gui.set_model(None)
        try:
            self.model.clear()
            self.nb_displayed = 0
            self._display_up_to(self.NB_EL_DISPLAYED_INITIALLY)
        finally:
            self.widget_gui.freeze_child_notify()
            self.widget_gui.set_model(self.model)

    def display_extra(self):
        self.__main_win.actions['open_doc'][1].enabled = False
        try:
            selected = self.widget_gui.get_selected_items()
            if len(selected) <= 0:
                selected = -1
            else:
                selected = min([x.get_indices()[0] for x in selected])

            (first_visible, last_visible) = self.widget_gui.get_visible_range()

            self.widget_gui.freeze_child_notify()
            self.widget_gui.set_model(None)
            try:
                self._display_up_to(self.nb_displayed +
                                    self.NB_EL_DISPLAYED_ADDITIONNAL)
            finally:
                self.widget_gui.freeze_child_notify()
                self.widget_gui.set_model(self.model)

            if (selected > 0):
                path = Gtk.TreePath(selected)
                self.widget_gui.select_path(path)
                self.widget_gui.set_cursor(path, None, False)

            GObject.idle_add(self.widget_gui.scroll_to_path, last_visible,
                             False, 0.0, 0.0)
        finally:
            self.__main_win.actions['open_doc'][1].enabled = True

    def _display_up_to(self, nb_elements):
        l_model = len(self.model)
        if l_model > 0:
            doc = self.model[-1][2]
            if doc is None or doc == 0:
                line_iter = self.model.get_iter(l_model-1)
                self.model.remove(line_iter)

        newly_displayed = []
        for line_idx in xrange(self.nb_displayed, nb_elements):
            if (self.nb_displayed >= nb_elements
                    or line_idx >= len(self.model_content)):
                break
            newly_displayed.append((line_idx, self.model_content[line_idx][2]))
            self.model.append(self.model_content[line_idx])
            self.nb_displayed += 1

        self.emit('lines-shown', newly_displayed)

        if nb_elements < len(self.model_content):
            self.model.append([_("Loading ..."),
                               self.__main_win.default_thumbnail, None])

        logger.info("List '%s' : %d elements displayed (%d additionnal)"
                    % (self.name, self.nb_displayed, len(newly_displayed)))

    def __on_scrollbar_moved(self):
        if self.nb_displayed >= len(self.model_content):
            return

        lower = self._vadjustment.get_lower()
        upper = self._vadjustment.get_upper()
        val = self._vadjustment.get_value()
        proportion = (val - lower) / (upper - lower)

        if proportion > self.NB_EL_DISPLAY_EXTRA_WHEN_LOWER_THAN:
            self.__main_win.schedulers['main'].cancel_all(self.job_factory)
            job = self.job_factory.make()
            self.__main_win.schedulers['main'].schedule(job)

    def set_model_value(self, line_idx, column_idx, value):
        self.model_content[line_idx][column_idx] = value
        if line_idx < self.nb_displayed:
            line_iter = self.model.get_iter(line_idx)
            self.model.set_value(line_iter, column_idx, value)

    def set_model_line(self, line_idx, model_line):
        self.model_content[line_idx] = model_line
        if line_idx < self.nb_displayed:
            self.model[line_idx] = model_line

    def pop(self, idx):
        content = self.model_content.pop(idx)
        itr = self.model.get_iter(idx)
        self.model.remove(itr)
        return content

    def insert(self, idx, line):
        self.model_content.insert(idx, line)
        self.model.insert(idx, line)

    def select_idx(self, idx=-1):
        if idx >= 0:
            # we are going to select the current page in the list
            # except we don't want to be called again because of it
            self.__main_win.actions['open_doc'][1].enabled = False
            try:
                self.widget_gui.unselect_all()

                path = Gtk.TreePath(idx)
                self.widget_gui.select_path(path)
                self.widget_gui.set_cursor(path, None, False)
            finally:
                self.__main_win.actions['open_doc'][1].enabled = True

            # HACK(Jflesch): The Gtk documentation says that scroll_to_path()
            # should do nothing if the target cell is already visible (which
            # is the desired behavior here). Except we just emptied the
            # document list model and remade it from scratch. For some reason,
            # it seems that  Gtk will then always consider that the cell is
            # not visible and move the scrollbar.
            # --> we use idle_add to move the scrollbar only once everything
            # has been displayed
            GObject.idle_add(self.widget_gui.scroll_to_path,
                             path, False, 0.0, 0.0)
        else:
            self.unselect()

    def unselect(self):
        self.widget_gui.unselect_all()
        path = Gtk.TreePath(0)
        GObject.idle_add(self.widget_gui.scroll_to_path,
                         path, False, 0.0, 0.0)

    def __getitem__(self, item):
        return {
            'gui': self.widget_gui,
            'model': self.model_content,
            'scrollbars': self.widget_scrollbars
        }[item]


GObject.type_register(ProgressiveList)


class MainWindow(object):
    def __init__(self, config):
        self.schedulers = {
            'main' : JobScheduler("Main"),
            'progress' : JobScheduler("Progress"),
        }

        # used by the set_mouse_cursor() function to keep track of how many
        # threads / jobs requested a busy mouse cursor
        self.__busy_mouse_counter = 0

        img = PIL.Image.new("RGB", (
            JobDocThumbnailer.THUMB_WIDTH,
            JobDocThumbnailer.THUMB_HEIGHT,
        ), color="#EEEEEE")
        img = add_img_border(img, JobDocThumbnailer.THUMB_BORDER)
        self.default_thumbnail = image2pixbuf(img)

        widget_tree = load_uifile("mainwindow.glade")

        self.window = widget_tree.get_object("mainWindow")

        self.__config = config
        self.__scan_start = 0.0
        self.__scan_progress_job = None

        self.docsearch = DummyDocSearch()
        self.doc = ImgDoc(self.__config.workdir)
        self.page = DummyPage(self.doc)

        search_completion = Gtk.EntryCompletion()

        self.lists = {
            'suggestions': {
                'gui': widget_tree.get_object("entrySearch"),
                'completion': search_completion,
                'model': widget_tree.get_object("liststoreSuggestion")
            },
            'doclist': [],
            'matches': ProgressiveList(
                name='documents',
                main_win=self,
                gui=widget_tree.get_object("iconviewMatch"),
                scrollbars=widget_tree.get_object("scrolledwindowMatch"),
                model=widget_tree.get_object("liststoreMatch"),
            ),
            'pages': ProgressiveList(
                name='pages',
                main_win=self,
                gui=widget_tree.get_object("iconviewPage"),
                scrollbars=widget_tree.get_object("scrolledwindowPage"),
                model=widget_tree.get_object("liststorePage"),
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
            lambda x, docs: GObject.idle_add(self.__on_doc_lines_shown, docs))

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

        self.img = {
            "image": widget_tree.get_object("imagePageImg"),
            "scrollbar": widget_tree.get_object("scrolledwindowPageImg"),
            "viewport": {
                "widget": widget_tree.get_object("viewportImg"),
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
                widget_tree.get_object("eventboxImg"),
                widget_tree.get_object("popupmenuPage")
            ),
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
             lambda docs: None),
            (widget_tree.get_object("radiomenuitemSortByScanDate"),
             sort_documents_by_date),
        ]

        self.job_factories = {
            'boxes_refresher': JobFactoryBoxesRefresher(self),
            'boxes_selecter': JobFactoryBoxesSelecter(self),
            'doc_examiner': JobFactoryDocExaminer(self, config),
            'doc_thumbnailer': JobFactoryDocThumbnailer(self),
            'export_previewer': JobFactoryExportPreviewer(self),
            'img_builder': JobFactoryImgBuilder(self),
            'importer': JobFactoryImporter(self, config),
            'index_reloader' : JobFactoryIndexLoader(self, config),
            'index_updater': JobFactoryIndexUpdater(self, config),
            'label_deleter': JobFactoryLabelDeleter(self),
            'label_updater': JobFactoryLabelUpdater(self),
            'match_list': self.lists['matches'].job_factory,
            'ocr_redoer': JobFactoryOCRRedoer(self, config),
            'page_editor': JobFactoryPageEditor(self, config),
            'page_list': self.lists['pages'].job_factory,
            'page_thumbnailer': JobFactoryPageThumbnailer(self),
            'progress_updater': JobFactoryProgressUpdater(
                self.status['progress']),
            'searcher': JobFactoryDocSearcher(self, config),
            'single_scan': JobFactorySingleScan(self, config),
        }

        self.actions = {
            'new_doc': (
                [
                    widget_tree.get_object("menuitemNew"),
                    widget_tree.get_object("toolbuttonNew"),
                ],
                ActionNewDocument(self, config),
            ),
            'open_doc': (
                [
                    widget_tree.get_object("iconviewMatch"),
                ],
                ActionOpenSelectedDocument(self)
            ),
            'open_page': (
                [
                    widget_tree.get_object("iconviewPage"),
                ],
                ActionOpenPageSelected(self)
            ),
            'select_label': (
                [
                    widget_tree.get_object("treeviewLabel"),
                ],
                ActionLabelSelected(self)
            ),
            'single_scan': (
                [
                    widget_tree.get_object("imagemenuitemScanSingle"),
                    widget_tree.get_object("toolbuttonScan"),
                    widget_tree.get_object("menuitemScanSingle"),
                ],
                ActionSingleScan(self, config)
            ),
            'multi_scan': (
                [
                    widget_tree.get_object("imagemenuitemScanFeeder"),
                    widget_tree.get_object("menuitemScanFeeder"),
                ],
                ActionMultiScan(self, config)
            ),
            'import': (
                [
                    widget_tree.get_object("menuitemImport"),
                    widget_tree.get_object("menuitemImport1"),
                ],
                ActionImport(self, config)
            ),
            'print': (
                [
                    widget_tree.get_object("menuitemPrint"),
                    widget_tree.get_object("menuitemPrint1"),
                    widget_tree.get_object("toolbuttonPrint"),
                ],
                ActionPrintDoc(self)
            ),
            'open_export_doc_dialog': (
                [
                    widget_tree.get_object("menuitemExportDoc"),
                    widget_tree.get_object("menuitemExportDoc1"),
                    widget_tree.get_object("menuitemExportDoc2"),
                ],
                ActionOpenExportDocDialog(self)
            ),
            'open_export_page_dialog': (
                [
                    widget_tree.get_object("menuitemExportPage"),
                    widget_tree.get_object("menuitemExportPage1"),
                    widget_tree.get_object("menuitemExportPage2"),
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
                    widget_tree.get_object("menuitemSettings"),
                    widget_tree.get_object("toolbuttonSettings"),
                ],
                ActionOpenSettings(self, config)
            ),
            'quit': (
                [
                    widget_tree.get_object("menuitemQuit"),
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
                    widget_tree.get_object("menuitemOpenParentDir"),
                    widget_tree.get_object("menuitemOpenDocDir"),
                    widget_tree.get_object("toolbuttonOpenDocDir"),
                ],
                ActionOpenDocDir(self),
            ),
            'del_doc': (
                [
                    widget_tree.get_object("menuitemDestroyDoc"),
                    widget_tree.get_object("menuitemDestroyDoc2"),
                    widget_tree.get_object("toolbuttonDeleteDoc"),
                ],
                ActionDeleteDoc(self),
            ),
            'edit_page': (
                [
                    widget_tree.get_object("menuitemEditPage"),
                    widget_tree.get_object("menuitemEditPage1"),
                    widget_tree.get_object("menuitemEditPage2"),
                    widget_tree.get_object("toolbuttonEditPage"),
                ],
                ActionEditPage(self),
            ),
            'del_page': (
                [
                    widget_tree.get_object("menuitemDestroyPage"),
                    widget_tree.get_object("menuitemDestroyPage1"),
                    widget_tree.get_object("menuitemDestroyPage2"),
                    widget_tree.get_object("buttonDeletePage"),
                ],
                ActionDeletePage(self),
            ),
            'first_page': (
                [
                    widget_tree.get_object("menuitemFirstPage"),
                ],
                ActionMovePageIndex(self, False, 0),
            ),
            'prev_page': (
                [
                    widget_tree.get_object("menuitemPrevPage"),
                    widget_tree.get_object("toolbuttonPrevPage"),
                ],
                ActionMovePageIndex(self, True, -1),
            ),
            'next_page': (
                [
                    widget_tree.get_object("menuitemNextPage"),
                    widget_tree.get_object("toolbuttonNextPage"),
                ],
                ActionMovePageIndex(self, True, 1),
            ),
            'last_page': (
                [
                    widget_tree.get_object("menuitemLastPage"),
                ],
                ActionMovePageIndex(self, False, -1),
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
                ActionRebuildPage(self)
            ),
            'zoom_in': (
                [
                    widget_tree.get_object("menuitemZoomIn"),
                ],
                ActionZoomChange(self, 1)
            ),
            'zoom_out': (
                [
                    widget_tree.get_object("menuitemZoomOut"),
                ],
                ActionZoomChange(self, -1)
            ),
            'zoom_best_fit': (
                [
                    widget_tree.get_object("menuitemZoomBestFit"),
                ],
                ActionZoomSet(self, 0.0)
            ),
            'zoom_normal': (
                [
                    widget_tree.get_object("menuitemZoomNormal"),
                ],
                ActionZoomSet(self, 1.0)
            ),
            'start_search': (
                [
                    widget_tree.get_object("menuitemFindTxt"),
                ],
                ActionStartSearch(self)
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
                ActionUpdateSearchResults(self, refresh_pages=False),
            ),
            'toggle_label': (
                [
                    widget_tree.get_object("cellrenderertoggleLabel"),
                ],
                ActionToggleLabel(self),
            ),
            'show_all_boxes': (
                [
                    self.show_all_boxes
                ],
                ActionRefreshBoxes(self)
            ),
            'show_toolbar': (
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
            'redo_ocr_all': (
                [
                    widget_tree.get_object("menuitemReOcrAll"),
                ],
                ActionRedoAllOCR(self),
            ),
            'reindex': (
                [],
                ActionRefreshIndex(self, config, force=False),
            ),
            'reindex_from_scratch': (
                [
                    widget_tree.get_object("menuitemReindexAll"),
                ],
                ActionRefreshIndex(self, config, force=True),
            ),
            'edit_doc': (
                [
                    widget_tree.get_object("menuitemEditDoc1"),
                    widget_tree.get_object("toolbuttonEditDoc"),
                    widget_tree.get_object("menuitemEditDoc")
                ],
                ActionEditDoc(self, config),
            ),
            'about': (
                [
                    widget_tree.get_object("menuitemAbout"),
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
            + self.actions['first_page'][0]
            + self.actions['prev_page'][0]
            + self.actions['next_page'][0]
            + self.actions['last_page'][0]
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

        for widget in self.need_doc_widgets.union(self.need_page_widgets):
            widget.set_sensitive(False)

        for (popup_menu_name, popup_menu) in self.popup_menus.iteritems():
            assert(not popup_menu[0] is None)
            assert(not popup_menu[1] is None)
            # TODO(Jflesch): Find the correct signal
            # This one doesn't take into account the key to access these menus
            popup_menu[0].connect("button-press-event", self.__popup_menu_cb,
                                  popup_menu[0], popup_menu[1])

        self.img['eventbox'].add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.img['eventbox'].connect("leave-notify-event",
                                     self.__on_img_mouse_leave)
        self.img['eventbox'].connect("motion-notify-event",
                                     self.__on_img_mouse_motion)

        for widget in [self.lists['pages']['gui'],
                       self.lists['matches']['gui']]:
            widget.enable_model_drag_dest([], Gdk.DragAction.MOVE)
            widget.drag_dest_add_text_targets()

        self.lists['pages']['gui'].connect(
            "drag-data-get", self.__on_page_list_drag_data_get_cb)
        self.lists['pages']['gui'].connect(
            "drag-data-received", self.__on_page_list_drag_data_received_cb)
        self.lists['matches']['gui'].connect(
            "drag-data-received", self.__on_match_list_drag_data_received_cb)

        self.window.connect("destroy",
                            ActionRealQuit(self, config).on_window_close_cb)

        self.img['image'].connect_after('draw', self.__on_img_draw)

        self.img['viewport']['widget'].connect("size-allocate",
                                               self.__on_img_resize_cb)

        self.window.set_visible(True)

        for scheduler in self.schedulers.values():
            scheduler.start()


    def set_search_availability(self, enabled):
        for list_view in self.doc_browsing.values():
            list_view.set_sensitive(enabled)

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

        job = self.job_factories['index_reloader'].make()
        self.schedulers['main'].schedule(job)

    def on_index_update_write_cb(self, src):
        self.set_search_availability(False)

    def on_search_result_cb(self, documents, suggestions):
        self.schedulers['main'].cancel_all(self.job_factories['doc_thumbnailer'])


        logger.debug("Got %d suggestions" % len(suggestions))
        self.lists['suggestions']['gui'].freeze_child_notify()
        try:
            self.lists['suggestions']['model'].clear()
            for suggestion in suggestions:
                self.lists['suggestions']['model'].append([suggestion])
        finally:
            self.lists['suggestions']['gui'].thaw_child_notify()

        logger.debug("Got %d documents" % len(documents))

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

    def on_page_thumbnailing_start_cb(self, src):
        self.set_progression(src, 0.0, _("Loading thumbnails ..."))
        self.set_mouse_cursor("Busy")

    def on_page_thumbnailing_page_done_cb(self, src, page_idx, thumbnail):
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

    def on_img_building_start(self, warn_user):
        if not warn_user:
            return
        self.drop_boxes()
        self.set_mouse_cursor("Busy")
        self.img['image'].set_from_stock(Gtk.STOCK_EXECUTE,
                                         Gtk.IconSize.DIALOG)

    def on_img_building_result_stock(self, warned_user, img):
        self.img['image'].set_from_stock(img, Gtk.IconSize.DIALOG)
        if warned_user:
            self.set_mouse_cursor("Normal")

    def on_img_building_result_clear(self, warned_user):
        self.img['image'].clear()
        if warned_user:
            self.set_mouse_cursor("Normal")

    def on_img_building_canceled(self, warned_user):
        if warned_user:
            self.set_mouse_cursor("Normal")

    def on_img_building_result_pixbuf(self, builder, warned_user, factor,
                                      original_width, pixbuf, boxes):
        self.img['boxes']['all'] = boxes

        self.img['factor'] = factor
        self.img['pixbuf'] = pixbuf
        self.img['original_width'] = original_width

        self.img['image'].set_from_pixbuf(pixbuf)

        self.refresh_boxes()

        if warned_user:
            self.set_mouse_cursor("Normal")

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

    def on_redo_ocr_start_cb(self, src):
        self.set_search_availability(False)
        self.set_mouse_cursor("Busy")
        self.set_progression(src, 0.0, _("Redoing OCR ..."))

    def on_redo_ocr_doc_updated_cb(self, src, progression, doc_name):
        self.set_progression(src, progression,
                             _("Redoing OCR (%s) ...") % (doc_name))

    def on_redo_ocr_end_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")
        self.refresh_label_list()
        # in case the keywords were highlighted
        self.show_page(self.page, force_refresh=True)
        self.actions['reindex'][1].do()

    def on_single_scan_start(self, job):
        self.set_progression(job, 0.0, _("Scanning ..."))
        self.set_mouse_cursor("Busy")
        self.img['image'].set_from_stock(Gtk.STOCK_EXECUTE,
                                         Gtk.IconSize.DIALOG)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(False)
        self.__scan_start = time.time()

        self.__scan_progress_job = self.job_factories['progress_updater'].make(
            value_min=0.0, value_max=0.5,
            total_time=self.__config.scan_time['normal'])
        self.schedulers['progress'].schedule(self.__scan_progress_job)

    def on_single_scan_ocr(self, job):
        scan_stop = time.time()
        self.schedulers['progress'].cancel(self.__scan_progress_job)
        self.__config.scan_time['normal'] = scan_stop - self.__scan_start

        self.set_progression(job, 0.5, _("Reading ..."))

        self.__scan_start = time.time()
        self.__scan_progress_job = self.job_factories['progress_updater'].make(
            value_min=0.5, value_max=1.0,
            total_time=self.__config.scan_time['ocr'])
        self.schedulers['progress'].schedule(self.__scan_progress_job)

    def on_single_scan_done(self, job, page):
        scan_stop = time.time()
        self.schedulers['progress'].cancel(self.__scan_progress_job)
        self.__config.scan_time['ocr'] = scan_stop - self.__scan_start

        for widget in self.need_doc_widgets.union(self.doc_edit_widgets):
            widget.set_sensitive(True)

        self.set_progression(job, 0.0, None)
        self.set_mouse_cursor("Normal")
        self.refresh_page_list()

        assert(page is not None)
        self.doc = job.doc  # no need to call show_doc() here
        self.show_page(page, force_refresh=True)

        if job.doc.nb_pages <= 1:
            self.refresh_docs({job.doc}, redo_thumbnails=True)
        else:
            self.refresh_docs({job.doc}, redo_thumbnails=False)

    def on_single_scan_error(self, src, error):
        logger.error("Error while scanning: %s: %s" % (type(error), error))
        for widget in self.need_doc_widgets.union(self.doc_edit_widgets):
            widget.set_sensitive(True)

        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")
        self.refresh_page_list()
        self.refresh_docs({self.doc})

        flags = (Gtk.DialogFlags.MODAL
                 | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        msg = _("Error while scanning: %s") % (error)
        dialog = Gtk.MessageDialog(
            parent=self.window,
            flags=flags,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=msg)
        dialog.run()
        dialog.destroy()


    def on_import_start(self, src):
        self.set_progression(src, 0.0, _("Importing ..."))
        self.set_mouse_cursor("Busy")
        self.img['image'].set_from_stock(Gtk.STOCK_EXECUTE,
                                         Gtk.IconSize.DIALOG)
        self.__scan_progress_job = self.job_factories['progress_updater'].make(
            value_min=0.0, value_max=0.75,
            total_time=self.__config.scan_time['ocr'])
        self.schedulers['progress'].schedule(self.__scan_progress_job)
        self.__scan_start = time.time()

    def on_import_done(self, src, doc, page=None):
        scan_stop = time.time()
        self.schedulers['progress'].cancel(self.__scan_progress_job)
        # Note: don't update scan time here: OCR is not required for all
        # imports

        for widget in self.need_doc_widgets:
            widget.set_sensitive(True)

        self.set_progression(src, 0.0, None)
        self.set_mouse_cursor("Normal")
        self.show_doc(0, doc)  # will refresh the page list
        # Many documents may have been imported actually. So we still
        # refresh the whole list
        self.refresh_doc_list()
        if page is not None:
            self.show_page(page)

    def __popup_menu_cb(self, ev_component, event, ui_component, popup_menu):
        # we are only interested in right clicks
        if event.button != 3 or event.type != Gdk.EventType.BUTTON_PRESS:
            return
        popup_menu.popup(None, None, None, None, event.button, event.time)

    def __on_img_mouse_motion(self, event_box, event):
        self.schedulers['main'].cancel_all(
            self.job_factories['boxes_selecter'])
        job = self.job_factories['boxes_selecter'].make(
            self.img['boxes']['all'], event.get_coords(),
            lambda box: self.__get_box_position(box, window=self.img['image'],
                                                width=0))
        self.schedulers['main'].schedule(job)

    def __queue_box_draw(self, boxes):
        for box in boxes:
            position = self.__get_box_position(
                box, window=self.img['image'], width=5)
            self.img['image'].queue_draw_area(position[0][0], position[0][1],
                                              position[1][0] - position[0][0],
                                              position[1][1] - position[0][1])

    def on_selected_boxes(self, selected):
        selected = set(selected)  # copy
        to_refresh = set(self.img['boxes']['selected'])
        to_refresh = to_refresh.union(selected)

        self.img['boxes']['selected'] = [x for x in selected]

        if len(selected) > 0:
            box = selected.pop()
            self.img['image'].set_tooltip_text(box.content)
        else:
            self.img['image'].set_has_tooltip(False)

        self.__queue_box_draw(to_refresh)

    def __on_img_mouse_leave(self, event_box, event):
        to_refresh = self.img['boxes']['selected']

        self.img['boxes']['selected'] = []
        self.img['image'].set_has_tooltip(False)

        for box in to_refresh:
            position = self.__get_box_position(
                box, window=self.img['image'], width=5)
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
        visible = []
        for line in self.img['boxes']['visible']:
            visible += line.word_boxes
        colors = [
            ((0.421875, 0.36328125, 0.81640625), 1, visible),
            ((0.421875, 0.36328125, 0.81640625), 2,
             self.img['boxes']['selected']),
            ((0.0, 0.62109375, 0.0), 2, self.img['boxes']['highlighted'])
        ]
        for ((color_r, color_b, color_g), line_width, boxes) in colors:
            cairo_context.set_source_rgb(color_r, color_b, color_g)
            cairo_context.set_line_width(line_width)

            for box in boxes:
                ((a, b), (c, d)) = self.__get_box_position(box, imgwidget,
                                                           width=line_width)
                cairo_context.rectangle(a, b, c-a, d-b)
                cairo_context.stroke()

    @staticmethod
    def __get_doc_txt(doc):
        if doc is None:
            return ""
        labels = doc.labels
        final_str = "%s" % (doc.name)
        nb_pages = doc.nb_pages
        if nb_pages > 1:
            final_str += (_(" (%d pages)") % (doc.nb_pages))
        if len(labels) > 0:
            final_str += "\n  "
            final_str += "\n  ".join([x.get_html() for x in labels])
        return final_str

    def __get_doc_model_line(self, doc):
        doc_txt = self.__get_doc_txt(doc)
        thumbnail = self.default_thumbnail
        if doc.nb_pages <= 0:
            thumbnail = None
        return ([
            doc_txt,
            thumbnail,
            doc,
        ])

    def __pop_new_doc(self):
        doc_list = self.lists['doclist']
        if (len(doc_list) <= 0 or not doc_list[0].is_new):
            return False
        doc_list.pop(0)
        self.lists['matches'].pop(0)
        return True

    def __insert_doc(self, doc_idx, doc):
        doc_list = self.lists['doclist']
        doc_list.insert(doc_idx, doc)
        doc_line = self.__get_doc_model_line(doc)
        self.lists['matches'].insert(doc_idx, doc_line)

    def __remove_doc(self, doc_idx):
        doc_list = self.lists['doclist']
        doc_list.pop(doc_idx)
        self.lists['matches'].pop(doc_idx)

    def __insert_new_doc(self):
        sentence = unicode(self.search_field.get_text(), encoding='utf-8')
        logger.info("Search: %s" % (sentence.encode('utf-8', 'replace')))

        # When a scan is done, we try to refresh only the current document.
        # However, the current document may be "New document". In which case
        # it won't appear as "New document" anymore. So we have to add a new
        # one to the list
        if sentence != u"":
            return False
        # append a new document to the list
        doc_list = self.lists['doclist']
        new_doc = ImgDoc(self.__config.workdir)
        doc_list.insert(0, new_doc)
        new_doc_line = self.__get_doc_model_line(new_doc)
        self.lists['matches'].insert(0, new_doc_line)
        return True

    def refresh_docs(self, docs, redo_thumbnails=True):
        """
        Refresh specific documents in the document list

        Arguments:
            docs --- Array of Doc
        """
        must_rethumbnail = set()

        for doc in set(docs):
            if doc.is_new:  # ASSUMPTION: was actually deleted
                doc_list = self.lists['doclist']
                idx = doc_list.index(doc)
                logger.info("Doc list refresh: %d:%s deleted"
                            % (idx, doc.docid))
                self.__remove_doc(idx)
                docs.remove(doc)

        if self.__pop_new_doc():
            logger.info("Doc list refresh: 'new doc' popped out of the list")

        # make sure all the target docs are already in the list in a first
        # place
        # XXX(Jflesch): this may screw up the document sorting
        doc_list = self.lists['doclist']
        doc_list = {doc_list[x]: x for x in xrange(0, len(doc_list))}
        for doc in set(docs):
            if not doc in doc_list:
                logger.info("Doc list refresh: 0:%s added"
                            % doc.docid)
                self.__insert_doc(0, doc)
                must_rethumbnail.add(doc)
                docs.remove(doc)

        if self.__insert_new_doc():
            logger.info("Doc list refresh: 'new doc' reinserted in the list")

        # Update the model of the remaining target docs
        doc_list = self.lists['doclist']
        doc_list = {doc_list[x]: x for x in xrange(0, len(doc_list))}
        for doc in set(docs):
            assert(doc in doc_list)
            doc_idx = doc_list[doc]
            logger.info("Doc list refresh: %d:%s refreshed"
                        % (doc_idx, doc.docid))
            doc_txt = self.__get_doc_txt(doc)
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
            self.docsearch, self.get_doc_sort_func(), search)
        self.schedulers['main'].schedule(job)

    def refresh_page_list(self):
        """
        Reload and refresh the page list.
        Warning: Will remove the thumbnails on all the pages
        """
        self.schedulers['main'].cancel_all(self.job_factories['page_thumbnailer'])

        model = [
            [
                _('Page %d') % (page.page_nb + 1),
                self.default_thumbnail,
                page.page_nb
            ] for page in self.doc.pages
        ]
        self.lists['pages'].set_model(model)

        self.indicators['total_pages'].set_text(
            _("/ %d") % (self.doc.nb_pages))
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(self.doc.can_edit)
        for widget in self.need_page_widgets:
            widget.set_sensitive(False)

        search = unicode(self.search_field.get_text(), encoding='utf-8')
        job = self.job_factories['page_thumbnailer'].make(self.doc, search)
        self.schedulers['main'].schedule(job)

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

    def on_highlighted_boxes(self, highlighted):
        prev_highlighted = set(self.img['boxes']['highlighted'])
        self.img['boxes']['highlighted'] = highlighted

        if self.show_all_boxes.get_active():
            self.img['boxes']['visible'] = self.img['boxes']['all']
            to_refresh = self.img['boxes']['all']
        else:
            self.img['boxes']['visible'] = []
            to_refresh = prev_highlighted.union(set(highlighted))

        self.__queue_box_draw(to_refresh)

    def refresh_boxes(self):
        self.schedulers['main'].cancel_all(self.job_factories['boxes_refresher'])
        search = unicode(self.search_field.get_text(), encoding='utf-8')
        job = self.job_factories['boxes_refresher'].make(self.page, search)
        self.schedulers['main'].schedule(job)

    def show_page(self, page, force_refresh=False):
        if (page == self.page and not force_refresh):
            return
        logging.info("Showing page %s" % page)

        self.schedulers['main'].cancel_all(self.job_factories['img_builder'])

        if self.export['exporter'] is not None:
            logging.info("Canceling export")
            self.actions['cancel_export'][1].do()

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

        job = self.job_factories['img_builder'].make(page)
        self.schedulers['main'].schedule(job)

    def show_doc(self, doc_idx, doc, force_refresh=False):
        if (self.doc is not None and self.doc == doc and not force_refresh):
            return
        self.doc = doc

        is_new = doc.is_new
        can_edit = doc.can_edit

        for widget in self.need_doc_widgets:
            widget.set_sensitive(True)
        for widget in self.doc_edit_widgets:
            widget.set_sensitive(True)
        for widget in self.need_doc_widgets:
            if is_new:
                widget.set_sensitive(False)
        for widget in self.doc_edit_widgets:
            if not can_edit:
                widget.set_sensitive(False)

        pages_gui = self.lists['pages']['gui']
        if doc.can_edit:
            pages_gui.enable_model_drag_source(0, [], Gdk.DragAction.MOVE)
            pages_gui.drag_source_add_text_targets()
        else:
            pages_gui.unset_model_drag_source()
        self.refresh_page_list()
        self.refresh_label_list()
        if doc.nb_pages > 0:
            self.show_page(doc.pages[0])
        else:
            self.img['image'].set_from_stock(Gtk.STOCK_MISSING_IMAGE,
                                             Gtk.IconSize.DIALOG)

    def on_export_preview_start(self):
        self.export['estimated_size'].set_text(_("Computing ..."))

    def on_export_preview_done(self, img_size, pixbuf):
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
        if pixbuf_width is None:
            pixbuf_width = self.img['original_width']
        return float(wanted_width) / pixbuf_width

    def refresh_export_preview(self):
        self.img['image'].set_from_stock(Gtk.STOCK_EXECUTE,
                                         Gtk.IconSize.DIALOG)
        self.schedulers['main'].cancel_all(self.job_factories['export_previewer'])
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

        # check if zoom level is set to adjusted, if yes,
        # we must resize the image
        el_idx = self.lists['zoom_levels']['gui'].get_active()
        el_iter = self.lists['zoom_levels']['model'].get_iter(el_idx)
        factor = self.lists['zoom_levels']['model'].get_value(el_iter, 1)
        if factor != 0.0:
            return

        self.schedulers['main'].cancel_all(self.job_factories['img_builder'])
        job = self.job_factories['img_builder'].make(self.page,
                                                     warn_user=False)
        self.schedulers['main'].schedule(job)

    def on_page_editing_img_edit_start_cb(self, job, page):
        self.set_mouse_cursor("Busy")
        self.set_progression(job, 0.0, _("Updating the image ..."))

    def on_page_editing_ocr_cb(self, job, page):
        self.set_progression(job, 0.25, _("Redoing OCR ..."))

    def on_page_editing_index_upd_cb(self, job, page):
        self.set_progression(job, 0.75, _("Updating the index ..."))

    def on_page_editing_done_cb(self, job, page):
        self.set_progression(job, 0.0, "")
        self.set_mouse_cursor("Normal")
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
            logger.warn("[page list] drag-data-received: no target. aborting")
            drag_context.finish(False, False, time)
            return
        (target_path, position) = target
        if target_path is None:
            logger.warn("[page list] drag-data-received: no target. aborting")
            drag_context.finish(False, False, time)
            return
        target = target_path.get_indices()[0]
        target_idx = self.lists['pages']['model'][target][2]
        if position == Gtk.IconViewDropPosition.DROP_BELOW:
            target_idx += 1

        assert(target_idx >= 0)
        obj_id = selection_data.get_text()

        logger.info("[page list] drag-data-received: %s -> %s" % (obj_id, target_idx))
        obj = self.docsearch.get_by_id(obj_id)
        if (target_idx >= obj.doc.nb_pages):
            target_idx = obj.doc.nb_pages - 1

        # TODO(Jflesch): Instantiate an ActionXXX to do that, so
        # this action can be cancelled later
        obj.change_index(target_idx)

        drag_context.finish(True, False, time)
        GObject.idle_add(self.refresh_page_list)
        doc = obj.doc
        GObject.idle_add(self.refresh_docs, {doc})

    def __on_match_list_drag_data_received_cb(self, widget, drag_context, x, y,
                                              selection_data, info, time):
        obj_id = selection_data.get_text()
        target = self.lists['matches']['gui'].get_dest_item_at_pos(x, y)
        if target is None:
            logger.warn("[doc list] drag-data-received: no target. aborting")
            drag_context.finish(False, False, time)
            return
        (target_path, position) = target
        if target_path is None:
            logger.warn("[doc list] drag-data-received: no target. aborting")
            drag_context.finish(False, False, time)
            return
        target = target_path.get_indices()[0]
        target_doc = self.lists['matches']['model'][target][2]
        obj_id = selection_data.get_text()
        obj = self.docsearch.get_by_id(obj_id)

        if not target_doc.can_edit:
            logger.warn("[doc list] drag-data-received: Destination document"
                   " can't be modified")
            drag_context.finish(False, False, time)
            return

        if target_doc == obj.doc:
            logger.info("[doc list] drag-data-received: Source and destination docs"
                   " are the same. Nothing to do")
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
        GObject.idle_add(self.refresh_page_list)

        # the index update will start a doc list refresh when finished
        job = self.job_factories['index_updater'].make(
            docsearch=self.docsearch,
            new_docs=set(),
            upd_docs=upd_docs,
            del_docs=del_docs,
            optimize=False
        )
        self.schedulers['main'].schedule(job)

    def __on_doc_lines_shown(self, docs):
        job = self.job_factories['doc_thumbnailer'].make(docs)
        self.schedulers['main'].schedule(job)

    def get_doc_sort_func(self):
        for (widget, sort_func) in self.sortings:
            if widget.get_active():
                return sort_func
        return self.sortings[0][1]
