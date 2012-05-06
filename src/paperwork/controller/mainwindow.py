import os

import gettext

from paperwork.util import load_uifile

_ = gettext.gettext


class MainWindow(object):
    def __init__(self, config):
        self.config = config

        widget_tree = load_uifile("mainwindow.glade")

        self.listStores = {
            'suggestions' : widget_tree.get_object("liststoreSuggestion"),
            'labels' : widget_tree.get_object("liststoreLabel"),
            'matches' : widget_tree.get_object("liststoreMatch"),
            'pages' : widget_tree.get_object("liststorePage"),
            'zoomLevels' : widget_tree.get_object("liststoreZoom"),
        }

        self.actionItems = {
            # Basic actions: there should be at least 2 items to do each of
            # them
            'new' : [
                widget_tree.get_object("menuitemNew"),
                widget_tree.get_object("toolbuttonNew"),
            ],
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
            'quit' : [
                widget_tree.get_object("menuitemQuit"),
                widget_tree.get_object("toolbuttonQuit"),
            ],
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

