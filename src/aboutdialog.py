from util import load_uifile

class AboutDialog(object):
    def __init__(self):
        self.wTree = load_uifile("aboutdialog.glade")
        self.aboutdialog = self.wTree.get_object("aboutdialog")
        assert(self.aboutdialog)
        self._connect_signals()
        self.aboutdialog.set_visible(True)

    def _connect_signals(self):
        self.aboutdialog.connect("destroy", lambda x: self._destroy())
        self.aboutdialog.connect("response", lambda x, y: self._destroy())
        self.aboutdialog.connect("close", lambda x: self._destroy())

    def _destroy(self):
        self.wTree.get_object("aboutdialog").destroy()

