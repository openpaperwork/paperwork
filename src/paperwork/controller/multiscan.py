import gettext
import gobject

from paperwork.controller.actions import SimpleAction
from paperwork.controller.workers import Worker
from paperwork.controller.workers import WorkerQueue
from paperwork.model.doc import ScannedDoc
from paperwork.util import load_uifile

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

    def __init__(self, config, nb_pages, line_in_treeview, doc=None):
        Worker.__init__(self, "Document scanner (doc %d)" % (line_in_treeview))
        self.__config = config
        self.doc = doc
        self.nb_pages = nb_pages
        self.line_in_treeview = line_in_treeview

    def do(self, scan_src):
        if self.doc == None:
            self.doc = ScannedDoc(self.__config.workdir)
        for page in range(0, self.nb_pages):
            self.emit('scan-start', page, self.nb_pages)
            # TODO
            self.emit('ocr-start', page, self.nb_pages)
            # TODO
            self.emit('scan-done', page, self.nb_pages)


gobject.type_register(DocScanWorker)


class ActionAddDoc(SimpleAction):
    def __init__(self, multiscan_dialog, config):
        SimpleAction.__init__(self, "Add doc to the multi-scan list")
        self.__dialog = multiscan_dialog
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        docidx = len(self.__dialog.lists['docs']['model'])
        self.__dialog.lists['docs']['model'].append(
            [
                _("Document %d") % docidx,
                1, 0, DocScanWorker(self.__config, 1, docidx),
                True, "", True
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
        val = model.get_value(selection_iter, 6)
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
        line_idx = 0
        for line in self.__dialog.lists['docs']['model']:
            line[3].line_in_treeview = line_idx
            if line_idx != 0:
                line[0] = _("Document %d") % line_idx
            line_idx += 1


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
        (model, selection_iter) = self.__dialog.lists['docs']['gui'] \
                .get_selection().get_selected()
        if selection_iter == None:
            print "No doc selected"
            return
        line = model[selection_iter]
        line[1] = int(new_text)
        line[3].nb_pages = int(new_text)
        model[selection_iter] = line


class ActionScan(SimpleAction):
    def __init__(self, multiscan_dialog, config):
        SimpleAction.__init__(self, "Start multi-scan")
        self.__dialog = multiscan_dialog
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        for line in self.__dialog.lists['docs']['model']:
            self.__dialog.scan_queue.add_worker(line[3])
        if not self.__dialog.scan_queue.is_running:
            scanner = self.__config.get_scanner_inst()
            try:
                scanner.options['source'].value = "ADF"
            except pyinsane.rawapi.SaneException, exc:
                print ("Warning: Unable to set scanner source to 'Auto': %s" %
                       (str(exc)))
            try:
                scanner.options['resolution'].value = \
                        self.__config.scanner_resolution
            except pyinsane.rawapi.SaneException:
                print ("Warning: Unable to set scanner resolution to %d: %s" %
                       (self.__config.scanner_resolution, str(exc)))
            scan_src = scanner.scan(multiple=True)
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
        'need-reindex' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, main_window, config):
        gobject.GObject.__init__(self)

        self.main_win = main_window
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
            },
        }

        self.lists['docs']['model'].clear()
        self.lists['docs']['model'].append([
            _("Current document (%s)") % (str(self.main_win.doc)), 0, 0,
            DocScanWorker(config, 0, 0, doc=self.main_win.doc),
            True, "", False
        ])
        self.lists['docs']['model'][0][3]

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
                ActionScan(self, config),
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
            self.lists['docs']['gui']
        ]

        self.scan_queue = WorkerQueue("Mutiple scans")
        self.scan_queue.connect("queue-start", lambda queue: \
                gobject.idle_add(self.__on_global_scan_start_cb, queue))
        self.scan_queue.connect("queue-stop", lambda queue, exc: \
                gobject.idle_add(self.__on_global_scan_end_cb, queue, exc))

        self.dialog = widget_tree.get_object("dialogMultiscan")
        self.dialog.set_transient_for(main_window.window)
        self.dialog.set_visible(True)


    def __on_global_scan_start_cb(self, work_queue):
        for el in self.to_disable_on_scan:
            el.set_sensitive(False)

    def __on_global_scan_end_cb(self, work_queue, exception=None):
        if exception != None:
            if isinstance(exception, StopIteration):
                # TODO
                pass
            return
        self.dialog.destroy()

gobject.type_register(MultiscanDialog)
