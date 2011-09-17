from util import load_uifile

class AboutDialog(object):
    def __init__(self):
        self.wTree = load_uifile("dtgrep.glade")
        self.aboutdialog = self.wTree.get_object("aboutdialog")
        assert(self.aboutdialog)
        self.connect_signals()
        self.aboutdialog.set_visible(True)

    def connect_signals(self):
        self.aboutdialog.connect("destroy", lambda x: self.destroy())
        self.aboutdialog.connect("response", lambda x, y: self.destroy())
        self.aboutdialog.connect("close", lambda x: self.destroy())

    def destroy(self):
        self.wTree.get_object("aboutdialog").destroy()

