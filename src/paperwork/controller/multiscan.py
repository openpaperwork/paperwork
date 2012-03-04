"""
Dialog to scan many pages and document at once
"""

import gettext

from paperwork.util import load_uifile

_ = gettext.gettext

class MultiscanDialog(object):
    def __init__(self, mainwindow, config, device):
        self.__mainwindow = mainwindow
        self.__config = config
        self.__device = device
        self.__widget_tree = load_uifile("multiscan.glade")

        # array of integers (nb_pages)
        self.__scan_list = [ (1, 0) ]

        self.__multiscan_dialog = \
                self.__widget_tree.get_object("dialogMultiscan")
        self.__scan_list_model = \
                self.__widget_tree.get_object("liststoreScanList")
        self.__scan_list_ui = self.__widget_tree.get_object("treeviewScanList")
        self.__nb_pages_column = \
                self.__widget_tree.get_object("treeviewcolumnNbPages")

        self.__multiscan_dialog.set_transient_for(mainwindow.main_window)

        self.__connect_signals()

        self.__multiscan_dialog.set_visible(True)

    def __reload_scan_list(self):
        i = 0
        self.__scan_list_model.clear()
        for (nb_pages, progress) in self.__scan_list:
            self.__scan_list_model.append([
                _("Document %d") % (i+1),
                nb_pages,
                progress,
                i # line number
            ])
            i += 1

    def __destroy_cb(self, widget=None):
        self.__multiscan_dialog.destroy()

    def __modify_doc_cb(self, widget=None):
        selection_path = self.__scan_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No doc selected"
        line = selection_path[0].get_value(selection_path[1], 3)
        self.__scan_list_ui.set_cursor(line,
                                       self.__nb_pages_column,
                                       start_editing=True)

    def __add_doc_cb(self, widget=None):
        self.__scan_list.append((1, 0))
        self.__reload_scan_list()

    def __remove_doc_cb(self, widget=None):
        selection_path = self.__scan_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No doc selected"
            return True
        line = selection_path[0].get_value(selection_path[1], 3)
        self.__scan_list.remove(self.__scan_list[line])
        self.__reload_scan_list()
        return True

    def __nb_pages_edited_cb(self, cellrenderer, path, new_text):
        selection_path = self.__scan_list_ui.get_selection().get_selected()
        if selection_path[1] == None:
            print "No doc selected"
            return True

        line = selection_path[0].get_value(selection_path[1], 3)
        val = -1
        try:
            val = int(new_text)
        except ValueError, exc:
            pass
        if val < 0:
            print "Invalid value: %s" % (new_text)
            return False

        self.__scan_list[line] = (val, 0)
        self.__reload_scan_list()
        return True

    def __scan_all_cb(self, widget=None):
        # TODO
        pass

    def __connect_signals(self):
        self.__multiscan_dialog.connect("destroy", self.__destroy_cb)
        self.__widget_tree.get_object("buttonEditDoc").connect(
                "clicked", self.__modify_doc_cb)
        self.__widget_tree.get_object("buttonRemoveDoc").connect(
                "clicked", self.__remove_doc_cb)
        self.__widget_tree.get_object("buttonAddDoc").connect(
                "clicked", self.__add_doc_cb)
        self.__widget_tree.get_object("cellrenderertextNbPages").connect(
                "edited", self.__nb_pages_edited_cb)
        self.__widget_tree.get_object("buttonOk").connect(
                "clicked", self.__scan_all_cb)
        self.__widget_tree.get_object("buttonCancel").connect(
                "clicked", self.__destroy_cb)
