#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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

import os

import gettext
import logging
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from paperwork.frontend.multiscan.scan import PageScan
from paperwork.frontend.multiscan.scan import DocScan
from paperwork.frontend.multiscan.scan import PageScanDrawer
from paperwork.frontend.util import load_uifile
from paperwork.frontend.util.actions import SimpleAction
from paperwork.frontend.util.canvas import Canvas
from paperwork.frontend.util.config import get_scanner
from paperwork.frontend.util.dialog import popup_no_scanner_found


_ = gettext.gettext
logger = logging.getLogger(__name__)


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
            logger.warning("No doc selected")
            return
        (model, selection_iter) = selection.get_selected()
        if selection_iter is None:
            logger.warning("No doc selected")
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
            logger.warning("No doc selected")
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
            logger.warning("No doc selected")
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
            logger.warning("No doc selected")
            return
        line = model[selection_iter]
        int(new_text)  # make sure it's a valid number
        line[1] = new_text


class ActionScan(SimpleAction):

    def __init__(self, multiscan_win, config, docsearch, main_win):
        SimpleAction.__init__(self, "Start multi-scan")
        self.__multiscan_win = multiscan_win
        self.__config = config
        self.__docsearch = docsearch
        self.__main_win = main_win

    def __on_scan_error(self, exc):
        if isinstance(exc, StopIteration):
            msg = _("Scan failed: No paper found")
        else:
            msg = _("Scan failed: {}").format(str(exc))
        flags = (Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.__main_win.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.show_all()

    def do(self):
        SimpleAction.do(self)

        try:
            (dev, resolution) = get_scanner(
                self.__config,
                preferred_sources=["ADF", "Feeder"]
            )
        except Exception as exc:
            logger.warning("Exception while configuring scanner: %s: %s."
                           " Assuming scanner is not connected",
                           type(exc), exc)
            logger.exception(exc)
            popup_no_scanner_found(self.__multiscan_win.window)
            raise

        try:
            scan_session = dev.scan(multiple=True)
        except Exception as exc:
            logger.error("Exception while scanning: {}".format(exc))
            logger.exception(exc)
            self.__on_scan_error(exc)
            raise

        self.__multiscan_win.on_global_scan_start_cb()

        page_scans = []

        MARGIN = 10
        position = (MARGIN, MARGIN)

        rng = range(0, len(self.__multiscan_win.lists['docs']['model']))
        for line_idx in rng:
            line = self.__multiscan_win.lists['docs']['model'][line_idx]
            doc = None
            if line_idx == 0:
                doc = self.__main_win.doc
            nb_pages = int(line[1])
            total_pages = nb_pages
            doc_nb_pages = 0
            if doc:
                total_pages += doc.nb_pages
                doc_nb_pages = doc.nb_pages
            doc_scan = DocScan(doc)
            drawer = None
            for page_nb in range(doc_nb_pages, doc_nb_pages + nb_pages):
                page_scan = PageScan(self.__main_win, self.__multiscan_win,
                                     self.__config,
                                     resolution, scan_session,
                                     line_idx, doc_scan,
                                     page_nb, total_pages)
                drawer = PageScanDrawer(position)
                self.__multiscan_win.scan_canvas.add_drawer(drawer)
                page_scan.connect("scanworkflow-inst",
                                  drawer.set_scan_workflow)
                page_scans.append(page_scan)
                position = (position[0] + drawer.size[0] + MARGIN,
                            position[1])
            new_height = position[1] + MARGIN
            if drawer:
                new_height += drawer.size[1]
            position = (MARGIN, new_height)

        first_page_scan = page_scans[0]
        last_page_scan = None
        for page_scan in page_scans:
            if last_page_scan:
                last_page_scan.connect_next_page_scan(page_scan)
            last_page_scan = page_scan

        if last_page_scan:
            last_page_scan.connect(
                "done",
                lambda _: GLib.idle_add(
                    self.__multiscan_win.on_global_scan_end_cb)
            )
        if first_page_scan:
            first_page_scan.start_scan_workflow()


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

        self.main_window = main_window

        self.schedulers = {
            'main': main_window.schedulers['main'],
        }

        self.scanned_pages = 0

        self.__config = config

        widget_tree = load_uifile(
            os.path.join("multiscan", "multiscan.glade"))

        self.window = widget_tree.get_object("dialogMultiscan")

        scan_scrollbars = widget_tree.get_object("scrolledwindowScan")
        self.scan_canvas = Canvas(scan_scrollbars)
        self.scan_canvas.set_visible(True)
        scan_scrollbars.add(self.scan_canvas)

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
                           main_window),
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

    def on_scan_start_cb(self, page_scan):
        progression = ("%d / %d" % (page_scan.page_nb, page_scan.total_pages))
        self.lists['docs']['model'][page_scan.line_idx][1] = progression
        progression = (page_scan.page_nb * 100 / page_scan.total_pages)
        self.lists['docs']['model'][page_scan.line_idx][3] = progression
        self.lists['docs']['model'][page_scan.line_idx][4] = _("Scanning")

    def on_ocr_start_cb(self, page_scan):
        progression = ((page_scan.page_nb * 100 + 50) / page_scan.total_pages)
        self.lists['docs']['model'][page_scan.line_idx][3] = progression
        self.lists['docs']['model'][page_scan.line_idx][4] = _("Reading")

    def on_scan_done_cb(self, page_scan):
        progression = ("%d / %d" % (page_scan.page_nb + 1,
                                    page_scan.total_pages))
        self.lists['docs']['model'][page_scan.line_idx][1] = progression
        progression = ((page_scan.page_nb * 100 + 100) / page_scan.total_pages)
        self.lists['docs']['model'][page_scan.line_idx][3] = progression
        self.lists['docs']['model'][page_scan.line_idx][4] = _("Done")
        self.scanned_pages += 1

    def on_global_scan_end_cb(self):
        self.emit('need-doclist-refresh')
        self.set_mouse_cursor("Normal")
        msg = _("All the pages have been scanned")
        dialog = Gtk.MessageDialog(self.dialog,
                                   flags=Gtk.DialogFlags.MODAL,
                                   message_type=Gtk.MessageType.INFO,
                                   buttons=Gtk.ButtonsType.OK,
                                   message_format=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(self.dialog.destroy))
        dialog.show_all()

    def on_scan_error_cb(self, page_scan, exception):
        logger.warning("Scan failed: %s" % str(exception))
        logger.info("Scan job cancelled")

        self.emit('need-doclist-refresh')
        self.set_mouse_cursor("Normal")

        if isinstance(exception, StopIteration):
            msg = _("Less pages than expected have been Img"
                    " (got %d pages)") % (self.scanned_pages)
            dialog = Gtk.MessageDialog(self.dialog,
                                       flags=Gtk.DialogFlags.MODAL,
                                       message_type=Gtk.MessageType.WARNING,
                                       buttons=Gtk.ButtonsType.OK,
                                       message_format=msg)
            dialog.connect("response", lambda dialog, response:
                           GLib.idle_add(dialog.destroy))
            dialog.connect("response", lambda dialog, response:
                           GLib.idle_add(self.dialog.destroy))
            dialog.show_all()
        else:
            # TODO(Jflesch): Dialog
            raise exception

    def __on_destroy(self, window=None):
        logger.info("Multi-scan dialog destroyed")

GObject.type_register(MultiscanDialog)
