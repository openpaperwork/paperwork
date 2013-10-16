#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
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

import gettext
import logging
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

import pyinsane.abstract_th as pyinsane

from paperwork.frontend.actions import SimpleAction
from paperwork.frontend.jobs import Job, JobFactory, JobScheduler, JobFactoryProgressUpdater
from paperwork.backend.img.doc import ImgDoc
from paperwork.backend.img.page import ImgPage
from paperwork.util import load_uifile
from paperwork.util import maximize_scan_area
from paperwork.util import popup_no_scanner_found
from paperwork.util import set_scanner_opt


_ = gettext.gettext
logger = logging.getLogger(__name__)


class JobDocScan(Job):
    __gsignals__ = {
        'scan-start': (GObject.SignalFlags.RUN_LAST, None,
                       # current page / total
                       (GObject.TYPE_INT, GObject.TYPE_INT)),
        'ocr-start': (GObject.SignalFlags.RUN_LAST, None,
                      # current page / total
                      (GObject.TYPE_INT, GObject.TYPE_INT)),
        'scan-done': (GObject.SignalFlags.RUN_LAST, None,
                      # current page, total
                      (GObject.TYPE_PYOBJECT, GObject.TYPE_INT)),
        'scan-error': (GObject.SignalFlags.RUN_LAST, None,
                       # exception
                       (GObject.TYPE_PYOBJECT,)),
    }

    can_stop = True
    priority = 500

    def __init__(self, factory, id,
                 config, nb_pages, line_in_treeview, docsearch, doc,
                 scan_src):
        Job.__init__(self, factory, id)
        self.__config = config
        self.__scan_src = scan_src
        self.docsearch = docsearch
        self.doc = doc
        self.nb_pages = nb_pages
        self.line_in_treeview = line_in_treeview
        self.current_page = None

    def __progress_cb(self, progression, total, step=None):
        if progression == 0 and step == ImgPage.SCAN_STEP_OCR:
            self.emit('ocr-start', self.current_page, self.nb_pages)

    def do(self):
        if self.doc is None:
            self.doc = ImgDoc(self.__config.workdir)
        for self.current_page in range(0, self.nb_pages):
            self.emit('scan-start', self.current_page, self.nb_pages)
            try:
                self.doc.scan_single_page(self.__scan_src,
                                          self.__config.scanner_resolution,
                                          self.__config.scanner_calibration,
                                          self.__config.langs,
                                          self.__progress_cb)
                page = self.doc.pages[self.doc.nb_pages - 1]
                self.docsearch.index_page(page)
                self.emit('scan-done', page, self.nb_pages)
            except StopIteration, exc:
                logger.warning("Feeder appears to be empty and we "
                               "haven't scanned all the pages yet !")
                self.emit('scan-error', exc)
                self._wait(5.0, force=True)  # wait for all the jobs to be cancelled
                return
            except Exception, exc:
                logger.error("Error: Exception: %s" % str(exc))
                self.emit('scan-error', exc)
                self._wait(5.0, force=True)  # wait for all the jobs to be cancelled
                return
        self.current_page = None

    def stop(self, will_resume=False):
        if will_resume == False:
            self._stop_wait()

GObject.type_register(JobDocScan)


class JobSignalEmitter(Job):
    __gsignals__ = {
        'signal': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 400

    def __init__(self, factory, id):
        Job.__init__(self, factory, id)

    def do(self):
        self.emit('signal')

    def __str__(self):
        return Job.__str__(self) + " (signal emitter)"


GObject.type_register(JobSignalEmitter)


class JobFactoryDocScan(JobFactory):
    def __init__(self, multiscan_win, config, docsearch):
        JobFactory.__init__(self, "MultiDocScan")
        self.__config = config
        self.__multiscan_win = multiscan_win

    def make_head(self):
        job = JobSignalEmitter(self, next(self.id_generator))
        job.connect('signal',
                    lambda job: GObject.idle_add(
                        self.__multiscan_win.on_global_scan_start_cb))
        return job

    def make(self, nb_pages, line_in_treeview, docsearch, doc, scan_src):
        job = JobDocScan(self, next(self.id_generator),
                         self.__config, nb_pages, line_in_treeview, docsearch,
                         doc, scan_src)
        job.connect("scan-start",
                    lambda job, page, total:
                    GObject.idle_add(
                        self.__multiscan_win.on_scan_start_cb, job, page,
                        total))
        job.connect("ocr-start",
                    lambda job, page, total:
                    GObject.idle_add(
                        self.__multiscan_win.on_ocr_start_cb, job, page,
                        total))
        job.connect("scan-done",
                    lambda job, page, total:
                    GObject.idle_add(
                        self.__multiscan_win.on_scan_done_cb, job, page,
                        total))
        job.connect("scan-error",
                    lambda job, exc:
                    GObject.idle_add(self.__multiscan_win.on_scan_error_cb,
                                     exc))
        return job

    def make_tail(self):
        job = JobSignalEmitter(self, next(self.id_generator))
        job.connect('signal',
                    lambda job: GObject.idle_add(
                        self.__multiscan_win.on_global_scan_end_cb))
        return job


class ActionAddDoc(SimpleAction):
    def __init__(self, multiscan_dialog, config):
        SimpleAction.__init__(self, "Add doc to the multi-scan list")
        self.__dialog = multiscan_dialog
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        docidx = len(self.__dialog.lists['docs']['model'])
        if not self.__dialog.lists['docs']['include_current_doc']:
            docidx += 1
        self.__dialog.lists['docs']['model'].append(
            [
                _("Document %d") % docidx,
                "1",  # nb_pages
                True,  # can_edit (nb_pages)
                0,  # scan_progress_int
                "",  # scan_progress_txt
                True  # can_delete
            ])


class ActionSelectDoc(SimpleAction):
    def __init__(self, multiscan_dialog):
        SimpleAction.__init__(self, "Doc selected in multi-scan list")
        self.__dialog = multiscan_dialog

    def do(self):
        SimpleAction.do(self)
        selection = self.__dialog.lists['docs']['gui'].get_selection()
        if selection is None:
            logger.warn("No doc selected")
            return
        (model, selection_iter) = selection.get_selected()
        if selection_iter is None:
            logger.warn("No doc selected")
            return
        val = model.get_value(selection_iter, 5)
        self.__dialog.removeDocButton.set_sensitive(val)


class ActionRemoveDoc(SimpleAction):
    def __init__(self, multiscan_dialog):
        SimpleAction.__init__(self, "Add doc to the multi-scan list")
        self.__dialog = multiscan_dialog

    def do(self):
        SimpleAction.do(self)
        docs_gui = self.__dialog.lists['docs']['gui']
        (model, selection_iter) = docs_gui.get_selection().get_selected()
        if selection_iter is None:
            logger.warn("No doc selected")
            return
        model.remove(selection_iter)
        for line_idx in range(0, len(self.__dialog.lists['docs']['model'])):
            line = self.__dialog.lists['docs']['model'][line_idx]
            if not self.__dialog.lists['docs']['include_current_doc']:
                line[0] = _("Document %d") % (line_idx + 1)
            elif line_idx != 0:
                line[0] = _("Document %d") % line_idx


class ActionStartEditDoc(SimpleAction):
    def __init__(self, multiscan_dialog):
        SimpleAction.__init__(self, "Start doc edit in multi-scan list")
        self.__dialog = multiscan_dialog

    def do(self):
        SimpleAction.do(self)
        docs_gui = self.__dialog.lists['docs']['gui']
        (model, selection_iter) = docs_gui.get_selection().get_selected()
        if selection_iter is None:
            logger.warn("No doc selected")
            return
        self.__dialog.lists['docs']['gui'].set_cursor(
            model.get_path(selection_iter),
            self.__dialog.lists['docs']['columns']['nb_pages'],
            start_editing=True)


class ActionEndEditDoc(SimpleAction):
    def __init__(self, multiscan_dialog):
        SimpleAction.__init__(self, "End doc edit in multi-scan list")
        self.__dialog = multiscan_dialog

    def do(self, new_text):
        SimpleAction.do(self, new_text=new_text)
        new_text = str(int(new_text))  # make sure it's a valid number
        docs_gui = self.__dialog.lists['docs']['gui']
        (model, selection_iter) = docs_gui.get_selection().get_selected()
        if selection_iter is None:
            logger.warn("No doc selected")
            return
        line = model[selection_iter]
        int(new_text)  # make sure it's a valid number
        line[1] = new_text


class ActionScan(SimpleAction):
    def __init__(self, multiscan_win, config, docsearch, main_win_doc):
        SimpleAction.__init__(self, "Start multi-scan")
        self.__multiscan_win = multiscan_win
        self.__config = config
        self.__docsearch = docsearch
        self.__main_win_doc = main_win_doc

    def do(self):
        SimpleAction.do(self)

        job = self.__multiscan_win.job_factories['scan'].make_head()
        self.__multiscan_win.schedulers['main'].schedule(job)
        try:
            try:
                scanner = self.__config.get_scanner_inst()
            except Exception:
                logger.error("No scanner found !")
                GObject.idle_add(popup_no_scanner_found,
                                 self.__multiscan_win.dialog)
                raise

            try:
                set_scanner_opt('source', scanner.options['source'],
                                ["ADF", ".*ADF.*", ".*Feeder.*"])
            except (KeyError, pyinsane.SaneException), exc:
                logger.error("Warning: Unable to set scanner source to 'Auto': %s"
                       % exc)
            maximize_scan_area(scanner)
            try:
                scan_src = scanner.scan(multiple=True)
            except Exception:
                logger.error("No scanner found !")
                GObject.idle_add(popup_no_scanner_found,
                                 self.__multiscan_win.dialog)
                raise

            rng = xrange(0, len(self.__multiscan_win.lists['docs']['model']))
            for line_idx in rng:
                line = self.__multiscan_win.lists['docs']['model'][line_idx]
                doc = None
                if line_idx == 0:
                    doc = self.__main_win_doc
                job = self.__multiscan_win.job_factories['scan'].make(
                    int(line[1]), line_idx, self.__docsearch, doc, scan_src)
                self.__multiscan_win.schedulers['main'].schedule(job)
        finally:
            job = self.__multiscan_win.job_factories['scan'].make_tail()
            self.__multiscan_win.schedulers['main'].schedule(job)


class ActionCancel(SimpleAction):
    def __init__(self, multiscan_win):
        SimpleAction.__init__(self, "Cancel multi-scan")
        self.__multiscan_win = multiscan_win

    def do(self):
        SimpleAction.do(self)
        self.__multiscan_win.dialog.destroy()


class MultiscanDialog(GObject.GObject):
    __gsignals__ = {
        'need-doclist-refresh': (GObject.SignalFlags.RUN_LAST, None, ()),
        'need-show-page': (GObject.SignalFlags.RUN_LAST, None,
                           (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self, main_window, config):
        GObject.GObject.__init__(self)

        self.schedulers = {
            'main': main_window.schedulers['main'],
        }

        self.scanned_pages = 0

        self.__config = config

        widget_tree = load_uifile("multiscan.glade")

        self.lists = {
            'docs': {
                'gui': widget_tree.get_object("treeviewScanList"),
                'model': widget_tree.get_object("liststoreScanList"),
                'columns': {
                    'nb_pages':
                    widget_tree.get_object("treeviewcolumnNbPages"),
                },
                'include_current_doc': False,
            },
        }

        self.removeDocButton = widget_tree.get_object("buttonRemoveDoc")
        self.removeDocButton.set_sensitive(False)

        self.job_factories = {
            'scan': JobFactoryDocScan(self, self.__config,
                                      main_window.docsearch)
        }

        actions = {
            'add_doc': (
                [widget_tree.get_object("buttonAddDoc")],
                ActionAddDoc(self, config),
            ),
            'select_doc': (
                [widget_tree.get_object("treeviewScanList")],
                ActionSelectDoc(self),
            ),
            'start_edit_doc': (
                [widget_tree.get_object("buttonEditDoc")],
                ActionStartEditDoc(self),
            ),
            'end_edit_doc': (
                [widget_tree.get_object("cellrenderertextNbPages")],
                ActionEndEditDoc(self),
            ),
            'del_doc': (
                [self.removeDocButton],
                ActionRemoveDoc(self),
            ),
            'cancel': (
                [widget_tree.get_object("buttonCancel")],
                ActionCancel(self)
            ),
            'scan': (
                [widget_tree.get_object("buttonOk")],
                ActionScan(self, config, main_window.docsearch,
                           main_window.doc),
            ),
        }

        for action in ['add_doc', 'select_doc', 'start_edit_doc',
                       'end_edit_doc', 'del_doc',
                       'scan', 'cancel']:
            actions[action][1].connect(actions[action][0])

        self.to_disable_on_scan = [
            actions['add_doc'][0][0],
            actions['start_edit_doc'][0][0],
            actions['del_doc'][0][0],
            actions['scan'][0][0],
        ]

        self.lists['docs']['model'].clear()
        if len(main_window.doc.pages) > 0 and main_window.doc.can_edit:
            self.lists['docs']['model'].append([
                _("Current document (%s)") % (str(main_window.doc)),
                "0",  # nb_pages
                True,  # can_edit (nb_pages)
                0,  # scan_progress_int
                "",  # scan_progress_txt
                False,  # can_delete
            ])
            self.lists['docs']['include_current_doc'] = True
        else:
            # add a first document to the list (the user will need one anyway)
            actions['add_doc'][1].do()

        self.dialog = widget_tree.get_object("dialogMultiscan")
        self.dialog.connect("destroy", self.__on_destroy)

        self.dialog.set_transient_for(main_window.window)
        self.dialog.set_visible(True)

    def set_mouse_cursor(self, cursor):
        self.dialog.get_window().set_cursor({
            "Normal": None,
            "Busy": Gdk.Cursor.new(Gdk.CursorType.WATCH),
        }[cursor])
        pass

    def on_global_scan_start_cb(self):
        for el in self.to_disable_on_scan:
            el.set_sensitive(False)
        for line in self.lists['docs']['model']:
            line[2] = False  # disable nb page edit
            line[5] = False  # disable deletion
        self.set_mouse_cursor("Busy")

    def on_scan_start_cb(self, job, current_page, total_pages):
        line_idx = job.line_in_treeview
        progression = ("%d / %d" % (current_page, total_pages))
        self.lists['docs']['model'][line_idx][1] = progression
        progression = (current_page*100/total_pages)
        self.lists['docs']['model'][line_idx][3] = progression
        self.lists['docs']['model'][line_idx][4] = _("Scanning")

    def on_ocr_start_cb(self, job, current_page, total_pages):
        line_idx = job.line_in_treeview
        progression = ((current_page*100+50)/total_pages)
        self.lists['docs']['model'][line_idx][3] = progression
        self.lists['docs']['model'][line_idx][4] = _("Reading")

    def on_scan_done_cb(self, job, page, total_pages):
        line_idx = job.line_in_treeview
        progression = ("%d / %d" % (page.page_nb + 1, total_pages))
        self.lists['docs']['model'][line_idx][1] = progression
        progression = ((page.page_nb*100+100)/total_pages)
        self.lists['docs']['model'][line_idx][3] = progression
        self.lists['docs']['model'][line_idx][4] = _("Done")
        self.scanned_pages += 1
        self.emit('need-show-page', page)

    def on_global_scan_end_cb(self):
        self.emit('need-doclist-refresh')
        self.set_mouse_cursor("Normal")
        msg = _("All the pages have been scanned")
        dialog = Gtk.MessageDialog(self.dialog,
                                   flags=Gtk.DialogFlags.MODAL,
                                   type=Gtk.MessageType.INFO,
                                   buttons=Gtk.ButtonsType.OK,
                                   message_format=msg)
        dialog.run()
        dialog.destroy()
        self.dialog.destroy()

    def on_scan_error_cb(self, exception):
        logger.warning("Scan failed: %s" % str(exception))
        self.schedulers['main'].cancel_all(self.job_factories['scan'])
        logger.info("Scan job cancelled")

        if isinstance(exception, StopIteration):
            msg = _("Less pages than expected have been Img"
                    " (got %d pages)") % (self.scanned_pages)
            dialog = Gtk.MessageDialog(self.dialog,
                                       flags=Gtk.DialogFlags.MODAL,
                                       type=Gtk.MessageType.WARNING,
                                       buttons=Gtk.ButtonsType.OK,
                                       message_format=msg)
            dialog.run()
            dialog.destroy()
        else:
            raise exception
        self.dialog.destroy()

    def __on_destroy(self, window=None):
        self.schedulers['main'].cancel_all(self.job_factories['scan'])
        logger.info("Multi-scan dialog destroyed")

GObject.type_register(MultiscanDialog)
