"""
Settings window.
"""

import gtk
import os

from util import load_uifile

class SettingsWindow(object):
    """
    Settings window.
    """
    OCR_LANGS = {
        "deu" : "German",
        "eng" : "English",
        "fra" : "French",
        "ita" : "Italian",
        "nld" : "Dutch",
        "port" : "Portuguese",
        "spa" : "Spanish",
        "vie" : "Vietnamese",
    }
    OCR_LANGS_REVERSE = dict((value, keyword) \
                             for keyword, value in OCR_LANGS.iteritems())

    def __init__(self, mainwindow, config):
        self.__mainwindow = mainwindow
        self.__config = config
        self.__widget_tree = load_uifile("settingswindow.glade")

        self.__settings_win = self.__widget_tree.get_object("windowSettings")
        self.__settings_win.set_transient_for(mainwindow.main_window)
        assert(self.__settings_win)

        self.__ocrlangs_widget = gtk.combo_box_new_text() # default

        self.__connect_signals()
        self.__fill_in_form()
        self.__settings_win.set_visible(True)

    def __apply(self):
        """
        Apply new user settings.
        """
        assert(self.__ocrlangs_widget)
        try:
            os.makedirs(self.__widget_tree \
                    .get_object("entrySettingsWorkDir").get_text())
        except OSError:
            pass
        self.__config.ocrlang = \
                self.OCR_LANGS_REVERSE[
                    self.__ocrlangs_widget.get_active_text()]
        if self.__config.workdir != \
                self.__widget_tree.get_object("entrySettingsWorkDir") \
                        .get_text():
            self.__config.workdir = \
                    self.__widget_tree.get_object("entrySettingsWorkDir") \
                        .get_text()
            self.__destroy()
            self.__mainwindow.new_document()
            self.__mainwindow.reindex()
        else:
            self.__destroy()
        self.__config.write()
        return True

    def __connect_signals(self):
        """
        Connect the GTK signals of the settings window.
        """
        self.__settings_win.connect("destroy", lambda x: self.__destroy())
        self.__widget_tree.get_object("buttonSettingsCancel").connect(
                "clicked", lambda x: self.__destroy())
        self.__widget_tree.get_object("buttonSettingsOk").connect(
                "clicked", lambda x: self.__apply())
        self.__widget_tree.get_object("buttonSettingsWorkDirSelect").connect(
                "clicked", lambda x: self.__open_file_chooser())

    def __fill_in_form(self):
        """
        Use the values from the Paperwork configuration to fill in the settings
        window.
        """
        # work dir
        self.__widget_tree.get_object("entrySettingsWorkDir").set_text(
            self.__config.workdir)

        # ocr lang
        table = self.__widget_tree.get_object("tableSettings")
        assert(table)
        self.__ocrlangs_widget = gtk.combo_box_new_text()
        idx = 0
        active_idx = 0
        for (shortname, longname) in self.OCR_LANGS.items():
            self.__ocrlangs_widget.append_text(longname)
            if shortname == self.__config.ocrlang:
                active_idx = idx
            idx = idx + 1
        self.__ocrlangs_widget.set_active(active_idx)
        self.__ocrlangs_widget.set_visible(True)
        table.attach(self.__ocrlangs_widget, 1, 2, 1, 2)

    def __open_file_chooser(self):
        """
        Called when the user want to choose the work directory of Paperwork
        """
        chooser = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                        buttons=(gtk.STOCK_CANCEL,
                                                 gtk.RESPONSE_CANCEL,
                                                 gtk.STOCK_OPEN,
                                                 gtk.RESPONSE_OK))
        chooser.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        chooser.set_current_folder(self.__widget_tree. \
                get_object("entrySettingsWorkDir").get_text())
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            print "Selected: %s" % (chooser.get_filename())
            self.__widget_tree.get_object("entrySettingsWorkDir") \
                    .set_text(chooser.get_filename())
        chooser.destroy()

    def __destroy(self):
        """
        Hide and destroy the settings window.
        """
        self.__widget_tree.get_object("windowSettings").destroy()

