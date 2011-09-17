import gtk

from util import load_uifile

class SearchWindow(object):
    def __init__(self, docsearch):
        self.docsearch = docsearch
        self.wTree = load_uifile("searchwindow.glade")

        self.searchwin = self.wTree.get_object("windowSearch")
        assert(self.searchwin)
        self.searchField = self.wTree.get_object("entrySearch")
        self.suggestionListUI = self.wTree.get_object("treeviewSuggestion")
        self.suggestionList = self.wTree.get_object("liststoreSuggestion")
        self.matchListUI = self.wTree.get_object("treeviewMatch")
        self.matchList = self.wTree.get_object("liststoreMatch")
        self.previewBox = self.wTree.get_object("imagePreview")

        self._connect_signals()
        self.searchwin.set_visible(True)

    def _update_results(self, objsrc = None):
        txt = unicode(self.searchField.get_text())
        print "Search: " + txt

        suggestions = self.docsearch.get_suggestions(txt.split(" "))
        print "Got %d suggestions" % len(suggestions)
        documents = self.docsearch.get_documents(txt.split(" "))
        print "Got %d documents" % len(documents)

        self.suggestionList.clear()
        for suggestion in suggestions:
            self.suggestionList.append([ suggestion ])
        self.matchList.clear()
        for document in documents:
            self.matchList.append([document])

    def _update_search_field(self, objsrc = None):
        selectionPath = self.suggestionListUI.get_selection().get_selected()
        if selectionPath[1] == None:
            return
        selection = selectionPath[0].get_value(selectionPath[1], 0)
        print "Selected suggestion: " + selection

        search = unicode(self.searchField.get_text())
        # TODO: i18n/l10n: spaces aren't always the correct word separator
        words = search.split(" ")
        search = ""
        for word in words:
            if search != "":
                search += " "
            if selection.startswith(word):
                search += selection
            else:
                search += word
        self.searchField.set_text(search)

    def _update_preview(self, objsrc = None):
        selectionPath = self.matchListUI.get_selection().get_selected()
        if selectionPath[1] == None:
            return
        selection = selectionPath[0].get_value(selectionPath[1], 0)
        print "Selected document: " + selection
        previewFile = self.docsearch.get_doc_img_filepath(selection, 1)
        print "Previewed file: " + previewFile

        pixbuf = gtk.gdk.pixbuf_new_from_file(previewFile)
        w = pixbuf.get_width() / 4
        h = pixbuf.get_height() / 4
        scaled_buf = pixbuf.scale_simple(w,h,gtk.gdk.INTERP_BILINEAR)
        self.previewBox.set_from_pixbuf(scaled_buf)
        self.previewBox.show()

    def _apply(self):
        # TODO
        return True

    def _connect_signals(self):
        self.searchwin.connect("destroy", lambda x: self._destroy())
        self.searchField.connect("changed", self._update_results)
        self.wTree.get_object("buttonSearchCancel").connect("clicked", lambda x: self._destroy())
        self.wTree.get_object("buttonSearchOk").connect("clicked", lambda x: self.apply() and self._destroy())
        self.suggestionListUI.connect("cursor-changed", self._update_search_field)
        self.matchListUI.connect("cursor-changed", self._update_preview)

    def _destroy(self):
        self.wTree.get_object("windowSearch").destroy()


