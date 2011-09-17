from util import load_uifile

class SearchWindow(object):
    def __init__(self, docsearch):
        self.docsearch = docsearch
        self.wTree = load_uifile("searchwindow.glade")
        self.searchwin = self.wTree.get_object("windowSearch")
        assert(self.searchwin)
        self.connect_signals()
        self.searchwin.set_visible(True)

    def update_results(self, objsrc):
        txt = self.wTree.get_object("entrySearch").get_text()
        print "Search: " + txt

    def apply(self):
        # TODO
        return True

    def connect_signals(self):
        self.searchwin.connect("destroy", lambda x: self.destroy())
        self.wTree.get_object("entrySearch").connect("changed", self.update_results)
        self.wTree.get_object("buttonSearchCancel").connect("clicked", lambda x: self.destroy())
        self.wTree.get_object("buttonSearchOk").connect("clicked", lambda x: self.apply() and self.destroy())

    def destroy(self):
        self.wTree.get_object("windowSearch").destroy()


