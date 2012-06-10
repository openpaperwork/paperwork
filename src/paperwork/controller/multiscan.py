import gobject

from paperwork.util import load_uifile

class MultiscanDialog(gobject.GObject):

    __gsignals__ = {
        'need-reindex' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, main_window, config):
        gobject.GObject.__init__(self)

        self.__main_win = main_window
        self.__config = config

        widget_tree = load_uifile("multiscan.glade")

        self.lists = {
            'docs' : (
                widget_tree.get_object("treeviewScanList"),
                widget_tree.get_object("liststoreScanList"),
            ),
        }

        self.actions = {
            'add_doc' : (
                [widget_tree.get_object("buttonAddDoc")],
            ),
            'edit_doc' : (
                [widget_tree.get_object("buttonEditDoc")],
            ),
            'del_doc' : (
                [widget_tree.get_object("buttonRemoveDoc")],
            ),
            'cancel' : (
                [widget_tree.get_object("buttonCancel")],
            ),
            'scan' : (
                [widget_tree.get_object("buttonOk")],
            ),
        }

        win = widget_tree.get_object("dialogMultiscan")
        win.set_transient_for(main_window.window)
        win.set_visible(True)


gobject.type_register(MultiscanDialog)
