import gtk

from util import load_uifile

class SettingsWindow(object):
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
    OCR_LANGS_REVERSE = dict((v,k) for k, v in OCR_LANGS.iteritems())

    def __init__(self, dtgrepConfig):
        self.dtgrepConfig = dtgrepConfig
        self.wTree = load_uifile("settingswindow.glade")
        self.settingswin = self.wTree.get_object("windowSettings")
        assert(self.settingswin)
        self.connect_signals()
        self.fill_in_form()
        self.settingswin.set_visible(True)

    def apply(self):
        assert(self.ocrlangs_widget)
        self.dtgrepConfig.workdir = self.wTree.get_object("entrySettingsWorkDir").get_text()
        self.dtgrepConfig.ocrlang = self.OCR_LANGS_REVERSE[self.ocrlangs_widget.get_active_text()]
        self.dtgrepConfig.write()
        return True

    def connect_signals(self):
        self.settingswin.connect("destroy", lambda x: self.destroy())
        self.wTree.get_object("buttonSettingsCancel").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("buttonSettingsOk").connect("clicked", lambda x: self.apply() and self.destroy())
        self.wTree.get_object("buttonSettingsWorkDirSelect").connect("clicked", lambda x: self.open_file_chooser())

    def fill_in_form(self):
        # work dir
        self.wTree.get_object("entrySettingsWorkDir").set_text(self.dtgrepConfig.workdir)

        # ocr lang
        wTable = self.wTree.get_object("tableSettings")
        assert(wTable)
        self.ocrlangs_widget = gtk.combo_box_new_text()
        idx = 0
        activeIdx = 0
        for (shortname, longname) in self.OCR_LANGS.items():
            self.ocrlangs_widget.append_text(longname)
            if shortname == self.dtgrepConfig.ocrlang:
                activeIdx = idx
            idx = idx + 1
        self.ocrlangs_widget.set_active(activeIdx)
        self.ocrlangs_widget.set_visible(True)
        wTable.attach(self.ocrlangs_widget, 1, 2, 1, 2)

    def open_file_chooser(self):
        chooser = gtk.FileChooserdialog(action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        chooser.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        chooser.set_current_folder(self.wTree.get_object("entrySettingsWorkDir").get_text())
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            print "Selected: %s" % (chooser.get_filename())
            self.wTree.get_object("entrySettingsWorkDir").set_text(chooser.get_filename())
        chooser.destroy()

    def destroy(self):
        self.wTree.get_object("windowSettings").destroy()

