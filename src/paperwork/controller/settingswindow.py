"""
Settings window.
"""

import Image
import ImageDraw
import os

import gettext
import gobject
import gtk
import pycountry
import pyocr.pyocr

from paperwork.controller.actions import SimpleAction
from paperwork.model.scanner import PaperworkScanner
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile

_ = gettext.gettext


class ActionApplySettings(SimpleAction):
    def __init__(self, settings_win, config):
        SimpleAction.__init__(self, "Apply settings")
        self.__settings_win = settings_win
        self.__config = config

    def do(self):
        workdir = self.__settings_win.workdir_chooser.get_current_folder()
        if workdir != self.__config.workdir:
            self.__config.workdir = workdir
            need_reindex = True

        self.__settings_win.hide()

        if need_reindex:
            self.__settings_win.emit("need-reindex")


class ActionCancelSettings(SimpleAction):
    def __init__(self, settings_win, config):
        SimpleAction.__init__(self, "Cancel settings")
        self.__settings_win = settings_win
        self.__config = config

    def do(self):
        self.__settings_win.display_config(self.__config)
        self.__settings_win.hide()


class SettingsWindow(gobject.GObject):
    """
    Settings window.
    """

    __gsignals__ = {
        'need-reindex' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, mainwindow_gui, config, scanner_mgmt):
        gobject.GObject.__init__(self)
        widget_tree = load_uifile("settingswindow.glade")

        self.window = widget_tree.get_object("windowSettings")
        self.window.set_transient_for(mainwindow_gui)

        self.workdir_chooser = widget_tree.get_object("filechooserbutton")

        self.display_config(config)

        actions = {
            "apply" : (
                [widget_tree.get_object("buttonSettingsOk")],
                ActionApplySettings(self, config)
            ),
            "cancel" : (
                [widget_tree.get_object("buttonSettingsCancel")],
                ActionCancelSettings(self, config)
            ),
        }

        for action in ["apply", "cancel"]:
            actions[action][1].connect(actions[action][0])

        self.window.set_visible(True)

    def display_config(self, config):
        self.workdir_chooser.set_current_folder(config.workdir)

    def hide(self):
        """
        Hide and destroy the settings window.
        """
        self.window.destroy()

gobject.type_register(SettingsWindow)
