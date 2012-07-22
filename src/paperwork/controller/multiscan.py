import gettext
import gobject
import gtk

from paperwork.controller.actions import SimpleAction
from paperwork.controller.workers import Worker
from paperwork.controller.workers import WorkerQueue
from paperwork.model.img.doc import ImgDoc
from paperwork.model.img.page import ImgPage
from paperwork.util import load_uifile
from paperwork.util import popup_no_scanner_found

_ = gettext.gettext


class DocScanWorker(Worker):
    __gsignals__ = {
        'scan-start' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                        # current page / total
                        (gobject.TYPE_INT, gobject.TYPE_INT)),
        'ocr-start' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                        # current page / total
                       (gobject.TYPE_INT, gobject.TYPE_INT)),
        'scan-done' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                        # current page / total
                       (gobject.TYPE_INT, gobject.TYPE_INT)),
    }

    can_interrupt = True

    def __init__(self, config, nb_pages, line_in_treeview, docsearch, doc=None):
        Worker.__init__(self, "Document scanner (doc %d)" % (line_in_treeview))
        self.__config = config
        self.docsearch = docsearch
        self.doc = doc
        self.nb_pages = nb_pages
        self.line_in_treeview = line_in_treeview
        self.current_page = None

    def __progress_cb(self, progression, total, step=None):
        if not self.can_run:
            raise Exception("Scan interrupted")
        if progression == 0 and step == ImgPage.SCAN_STEP_OCR:
            self.emit('ocr-start', self.current_page, self.nb_pages)

    def do(self, scan_src):
        if self.doc == None:
            self.doc = ImgDoc(self.__config.workdir)
        for self.current_page in range(0, self.nb_pages):
            self.emit('scan-start', self.current_page, self.nb_pages)
            self.doc.scan_single_page(scan_src,
                                      self.__config.scanner_resolution,
                                      self.__config.ocrlang,
                                      self.__config.scanner_calibration,
                                      self.__progress_cb)
            page = self.doc.pages[self.doc.nb_pages - 1]
            self.docsearch.index_page(page)
            self.emit('scan-done', self.current_page, self.nb_pages)
        self.current_page = None


gobject.type_register(DocScanWorker)


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
                "1", # nb_pages
                True, # can_edit (nb_pages)
                0, # scan_progress_int
                "", # scan_progress_txt
                True # can_delete
            ])


class ActionSelectDoc(SimpleAction):
    def __init__(self, multiscan_dialog):
        SimpleAction.__init__(self, "Doc selected in multi-scan list")
        self.__dialog = multiscan_dialog

    def do(self):
        SimpleAction.do(self)
        (model, selection_iter) = self.__dialog.lists['docs']['gui'] \
                .get_selection().get_selected()
        if selection_iter == None:
            print "No doc selected"
            return
        val = model.get_value(selection_iter, 5)
        self.__dialog.removeDocButton.set_sensitive(val)


class ActionRemoveDoc(SimpleAction):
    def __init__(self, multiscan_dialog):
        SimpleAction.__init__(self, "Add doc to the multi-scan list")
        self.__dialog = multiscan_dialog

    def do(self):
        SimpleAction.do(self)
        (model, selection_iter) = self.__dialog.lists['docs']['gui'] \
                .get_selection().get_selected()
        if selection_iter == None:
            print "No doc selected"
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
        (model, selection_iter) = self.__dialog.lists['docs']['gui'] \
                .get_selection().get_selected()
        if selection_iter == None:
            print "No doc selected"
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
        (model, selection_iter) = self.__dialog.lists['docs']['gui'] \
                .get_selection().get_selected()
        if selection_iter == None:
            print "No doc selected"
            return
        line = model[selection_iter]
        line[1] = int(new_text)
        model[selection_iter] = line


class ActionScan(SimpleAction):
    def __init__(self, multiscan_dialog, config, docsearch, main_win_doc):
        SimpleAction.__init__(self, "Start multi-scan")
        self.__dialog = multiscan_dialog
        self.__config = config
        self.__docsearch = docsearch
        self.__main_win_doc = main_win_doc

    def do(self):
        SimpleAction.do(self)
        try:
            scanner = self.__config.get_scanner_inst()
        except Exception:
            print "No scanner found !"
            gobject.idle_add(popup_no_scanner_found, self.__dialog.dialog)
            raise

        for line_idx in range(0, len(self.__dialog.lists['docs']['model'])):
            line = self.__dialog.lists['docs']['model'][line_idx]
            doc = None
            if line_idx == 0:
                doc = self.__main_win_doc
            worker = DocScanWorker(self.__config, nb_pages=int(line[1]),
                                   line_in_treeview=line_idx,
                                   docsearch=self.__docsearch,
                                   doc=doc)
            self.__dialog.scan_queue.add_worker(worker)
        if self.__dialog.scan_queue.is_running:
            return
        try:
            scanner.options['source'].value = "ADF"
        except pyinsane.rawapi.SaneException, exc:
            print ("Warning: Unable to set scanner source to 'Auto': %s" %
                   (str(exc)))
        try:
            scan_src = scanner.scan(multiple=True)
        except Exception:
            print "No scanner found !"
            gobject.idle_add(popup_no_scanner_found, self.__dialog.dialog)
            raise

        self.__dialog.scan_queue.start(scan_src=scan_src)


class ActionCancel(SimpleAction):
    def __init__(self, multiscan_dialog):
        SimpleAction.__init__(self, "Cancel multi-scan")
        self.__dialog = multiscan_dialog

    def do(self):
        SimpleAction.do(self)
        self.__dialog.dialog.destroy()


class MultiscanDialog(gobject.GObject):
    __gsignals__ = {
        'need-doclist-refresh' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, main_window, config):
        gobject.GObject.__init__(self)

        self.scanned_pages = 0

        self.__config = config

        widget_tree = load_uifile("multiscan.glade")

        self.lists = {
            'docs' : {
                'gui': widget_tree.get_object("treeviewScanList"),
                'model': widget_tree.get_object("liststoreScanList"),
                'columns' : {
                    'nb_pages' : \
                        widget_tree.get_object("treeviewcolumnNbPages"),
                },
                'include_current_doc': False,
            },
        }

        self.removeDocButton = widget_tree.get_object("buttonRemoveDoc")
        self.removeDocButton.set_sensitive(False)

        actions = {
            'add_doc' : (
                [widget_tree.get_object("buttonAddDoc")],
                ActionAddDoc(self, config),
            ),
            'select_doc' : (
                [widget_tree.get_object("treeviewScanList")],
                ActionSelectDoc(self),
            ),
            'start_edit_doc' : (
                [widget_tree.get_object("buttonEditDoc")],
                ActionStartEditDoc(self),
            ),
            'end_edit_doc' : (
                [widget_tree.get_object("cellrenderertextNbPages")],
                ActionEndEditDoc(self),
            ),
            'del_doc' : (
                [self.removeDocButton],
                ActionRemoveDoc(self),
            ),
            'cancel' : (
                [widget_tree.get_object("buttonCancel")],
                ActionCancel(self)
            ),
            'scan' : (
                [widget_tree.get_object("buttonOk")],
                ActionScan(self, config, main_window.docsearch, main_window.doc),
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

        self.scan_queue = WorkerQueue("Mutiple scans")
        self.scan_queue.connect("queue-start", lambda queue: \
                gobject.idle_add(self.__on_global_scan_start_cb, queue))
        self.scan_queue.connect("queue-stop", lambda queue, exc: \
                gobject.idle_add(self.__on_global_scan_end_cb, queue, exc))
        self.scan_queue.connect("scan-start", lambda worker, page, total: \
                gobject.idle_add(self.__on_scan_start_cb, worker, page, total))
        self.scan_queue.connect("ocr-start", lambda worker, page, total: \
                gobject.idle_add(self.__on_ocr_start_cb, worker, page, total))
        self.scan_queue.connect("scan-done", lambda worker, page, total: \
                gobject.idle_add(self.__on_scan_done_cb, worker, page, total))

        self.dialog = widget_tree.get_object("dialogMultiscan")
        self.dialog.connect("destroy", self.__on_destroy)


        self.dialog.set_transient_for(main_window.window)
        self.dialog.set_visible(True)


    def set_mouse_cursor(self, cursor):
        self.dialog.window.set_cursor({
            "Normal" : None,
            "Busy" : gtk.gdk.Cursor(gtk.gdk.WATCH),
        }[cursor])


    def __on_global_scan_start_cb(self, work_queue):
        for el in self.to_disable_on_scan:
            el.set_sensitive(False)
        for line in self.lists['docs']['model']:
            line[2] = False  # disable nb page edit
            line[5] = False  # disable deletion
        self.set_mouse_cursor("Busy")

    def __on_scan_start_cb(self, worker, current_page, total_pages):
        line_idx = worker.line_in_treeview
        self.lists['docs']['model'][line_idx][1] = \
                ("%d / %d" % (current_page, total_pages))
        self.lists['docs']['model'][line_idx][3] = \
                (current_page*100/total_pages)
        self.lists['docs']['model'][line_idx][4] = _("Scanning")

    def __on_ocr_start_cb(self, worker, current_page, total_pages):
        line_idx = worker.line_in_treeview
        self.lists['docs']['model'][line_idx][3] = \
                ((current_page*100+50)/total_pages)
        self.lists['docs']['model'][line_idx][4] = _("Reading")

    def __on_scan_done_cb(self, worker, current_page, total_pages):
        line_idx = worker.line_in_treeview
        self.lists['docs']['model'][line_idx][1] = \
                ("%d / %d" % (current_page+1, total_pages))
        self.lists['docs']['model'][line_idx][3] = \
                ((current_page*100+100)/total_pages)
        self.lists['docs']['model'][line_idx][4] = _("Done")
        self.scanned_pages += 1

    def __on_global_scan_end_cb(self, work_queue, exception=None):
        self.set_mouse_cursor("Normal")
        if exception != None:
            if isinstance(exception, StopIteration):
                msg = _("Less pages than expected have been Img"
                        " (got %d pages)") % (self.scanned_pages)
                dialog = gtk.MessageDialog(self.dialog,
                                           flags=gtk.DIALOG_MODAL,
                                           type=gtk.MESSAGE_WARNING,
                                           buttons=gtk.BUTTONS_OK,
                                           message_format=msg)
                dialog.run()
                dialog.destroy()
            else:
                raise exception
        else:
            msg = _("All the pages have been scanned")
            dialog = gtk.MessageDialog(self.dialog,
                                       flags=gtk.DIALOG_MODAL,
                                       type=gtk.MESSAGE_INFO,
                                       buttons=gtk.BUTTONS_OK,
                                       message_format=msg)
            dialog.run()
            dialog.destroy()
        self.dialog.destroy()
        self.emit('need-doclist-refresh')

    def __on_destroy(self, window=None):
        if self.scan_queue.is_running:
            self.scan_queue.stop()
        print "Multi-scan dialog destroyed"

gobject.type_register(MultiscanDialog)
