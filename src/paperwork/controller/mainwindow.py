import os

import gtk
import gettext

from paperwork.model.doc import ScannedDoc
from paperwork.util import load_uifile

_ = gettext.gettext

class ActionButton(object):
    """
    Template for all the actions started by buttons
    """
    def __init__(self, name):
        self.name = name

    def do(self):
        print "Action: %s" % (self.name)

    def button_clicked(self, toolbutton):
        self.do()

    def menuitem_activate(self, menuitem):
        self.do()


class ActionNewDocument(ActionButton):
    """
    Starts a new document.
    Warning: Won't change anything in the UI
    """
    def __init__(self, main_window, config):
        ActionButton.__init__(self, "New document")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        ActionButton.do(self)
        self.__main_win.doc = ScannedDoc(self.__config.workdir)


class ActionQuit(ActionButton):
    """
    Quit
    """
    def __init__(self, main_window):
        ActionButton.__init__(self, "Quit")
        self.__main_win = main_window

    def do(self):
        ActionButton.do(self)
        self.__main_win.window.destroy()
        gtk.main_quit()


class MainWindow(object):
    def __init__(self, config):
        widget_tree = load_uifile("mainwindow.glade")

        self.window = widget_tree.get_object("mainWindow")

        self.listStores = {
            'suggestions' : widget_tree.get_object("liststoreSuggestion"),
            'labels' : widget_tree.get_object("liststoreLabel"),
            'matches' : widget_tree.get_object("liststoreMatch"),
            'pages' : widget_tree.get_object("liststorePage"),
            'zoomLevels' : widget_tree.get_object("liststoreZoom"),
        }

        self.indicators = {
            'total_page' : widget_tree.get_object("labelTotalPages"),
        }

        self.listViews = {
            'matches' : widget_tree.get_object("treeviewMatch"),
            'pages' : widget_tree.get_object("iconviewPage"),
            'labels' : widget_tree.get_object("labels"),
        }

        self.text_area = widget_tree.get_object("textviewPageTxt")
        self.img_area = widget_tree.get_object("imagePageImg")

        self.status = {
            'progress' : widget_tree.get_object("progressbar"),
            'text' : widget_tree.get_object("statusbar"),
        }

        self.popupMenus = {
            'labels' : widget_tree.get_object("popupmenuLabels"),
            'matches' : widget_tree.get_object("popupmenuMatchs"),
            'pages' : widget_tree.get_object("popupmenuPages"),
        }

        self.actions = {
            # Basic actions: there should be at least 2 items to do each of
            # them
            'new' : (
                [
                    widget_tree.get_object("menuitemNew"),
                    widget_tree.get_object("toolbuttonNew"),
                ],
                [
                    ActionNewDocument(self, config),
                ]
            ),
            'single_scan' : [
                widget_tree.get_object("menuitemScan"),
                widget_tree.get_object("imagemenuitemScanSingle"),
                widget_tree.get_object("toolbuttonScan"),
                widget_tree.get_object("menuitemScanSingle"),
            ],
            'multi_scan' : [
                widget_tree.get_object("imagemenuitemScanFeeder"),
                widget_tree.get_object("menuitemScanFeeder"),
            ],
            'print' : [
                widget_tree.get_object("menuitemPrint"),
                widget_tree.get_object("toolbuttonPrint"),
            ],
            'settings' : [
                widget_tree.get_object("menuitemSettings"),
                # TODO
            ],
            'quit' : (
                [
                    widget_tree.get_object("menuitemQuit"),
                    widget_tree.get_object("toolbuttonQuit"),
                ],
                [
                    ActionQuit(self),
                ],
            ),
            'add_label' : [
                widget_tree.get_object("buttonAddLabel"),
                # TODO
            ],
            'edit_label' : [
                widget_tree.get_object("menuitemEditLabel"),
                widget_tree.get_object("buttonEditLabel"),
            ],
            'del_label' : [
                widget_tree.get_object("menuitemDestroyLabel"),
                widget_tree.get_object("buttonDelLabel"),
            ],
            'open_doc_dir' : [
                widget_tree.get_object("menuitemOpenDocDir"),
                widget_tree.get_object("toolbuttonOpenDocDir"),
            ],
            'del_doc' : [
                widget_tree.get_object("menuitemDestroyDoc2"),
                # TODO
            ],
            'del_page' : [
                widget_tree.get_object("menuitemDestroyPage2"),
                # TODO
            ],
            'prev_page' : [
                # the second way of doing that is clicking in the page list
                widget_tree.get_object("toolbuttonPrevPage"),
            ],
            'next_page' : [
                # the second way of doing that is clicking in the page list
                widget_tree.get_object("toolbuttonNextPage"),
            ],
            'current_page' : [
                # the second way of selecting a page is clicking in the page
                # list
                widget_tree.get_object("entryPageNb"),
            ],
            'zoom_levels' : [
                widget_tree.get_object("comboboxZoom"),
                # TODO
            ],

            # Advanced actions: having only 1 item to do them is fine
            'show_all_boxes' : [
                widget_tree.get_object("checkmenuitemShowAllBoxes"),
            ],
            'redo_ocr_doc': [
                widget_tree.get_object("menuitemReOcr"),
            ],
            'redo_ocr_all' : [
                widget_tree.get_object("menuitemReOcrAll"),
            ],
            'reindex' : [
                widget_tree.get_object("menuitemReindexAll"),
            ],
            'about' : [
                widget_tree.get_object("menuitemAbout"),
            ],
        }

        self.connectButtons(self.actions['new'][0],
                            self.actions['new'][1])
        self.connectButtons(self.actions['quit'][0],
                            self.actions['quit'][1])

        self.window.set_visible(True)

    @staticmethod
    def connectButtons(buttons, actions):
        for button in buttons:
            assert(button != None)
            for action in actions:
                if isinstance(button, gtk.ToolButton):
                    button.connect("clicked", action.button_clicked)
                elif isinstance(button, gtk.Button):
                    button.connect("clicked", action.button_clicked)
                elif isinstance(button, gtk.MenuItem):
                    button.connect("activate", action.menuitem_activate)
                else:
                    assert()
