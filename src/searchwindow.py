import gtk
import time

from util import gtk_refresh
from util import load_uifile
from util import strip_accents

class SearchWindow(object):
    def __init__(self, mainwindow, docsearch):
        self.mainwindow = mainwindow
        self.docsearch = docsearch
        self.wTree = load_uifile("searchwindow.glade")

        self.searchwin = self.wTree.get_object("windowSearch")
        assert(self.searchwin)

        self.liststoreSuggestion = self.wTree.get_object("liststoreSuggestion")
        self.searchField = self.wTree.get_object("entrySearch")
        self.searchCompletion = gtk.EntryCompletion()
        self.searchCompletion.set_model(self.liststoreSuggestion)
        self.searchCompletion.set_text_column(0)
        self.searchCompletion.set_match_func(lambda x, y, z: True)
        self.searchField.set_completion(self.searchCompletion)

        self.matchListUI = self.wTree.get_object("treeviewMatch")
        self.matchList = self.wTree.get_object("liststoreMatch")
        self.previewBox = self.wTree.get_object("imagePreview")

        self._connect_signals()
        self.searchwin.set_visible(True)
        self.searchField.set_completion(self.searchCompletion)

    def _adapt_search(self, search, suggestion):
        suggestion = strip_accents(suggestion)
        # TODO: i18n/l10n: spaces aren't always the correct word separator
        words = search.split(" ")
        search = ""
        for word in words:
            word = strip_accents(word)
            if search != "":
                search += " "
            if suggestion.startswith(word):
                search += suggestion
            else:
                search += word
        print "Suggestion: %s -> %s" % (suggestion, search)
        return search

    def _update_results(self, objsrc = None):
        txt = unicode(self.searchField.get_text())
        print "Search: %s" % txt

        suggestions = self.docsearch.get_suggestions(txt.split(" "))
        print "Got %d suggestions" % len(suggestions)
        self.liststoreSuggestion.clear()
        full_suggestions = []
        for suggestion in suggestions:
            full_suggestions.append(self._adapt_search(txt, suggestion))
        full_suggestions.sort()
        for suggestion in full_suggestions:
            self.liststoreSuggestion.append([suggestion])

        documents = self.docsearch.get_documents(txt.split(" "))
        print "Got %d documents" % len(documents)
        self.matchList.clear()
        for document in reversed(documents):
            self.matchList.append([document])

    def _update_preview(self, objsrc = None):
        selectionPath = self.matchListUI.get_selection().get_selected()
        if selectionPath[1] == None:
            return
        selection = selectionPath[0].get_value(selectionPath[1], 0)
        print "Selected document: " + selection
        previewFile = self.docsearch.get_doc(selection).get_img_path(1)
        print "Previewed file: " + previewFile

        pixbuf = gtk.gdk.pixbuf_new_from_file(previewFile)
        w = pixbuf.get_width() / 4
        h = pixbuf.get_height() / 4
        scaled_buf = pixbuf.scale_simple(w,h,gtk.gdk.INTERP_BILINEAR)
        self.previewBox.set_from_pixbuf(scaled_buf)
        self.previewBox.show()

    def _apply(self):
        selectionPath = self.matchListUI.get_selection().get_selected()
        if selectionPath[1] == None:
            print "No document selected. Can't open"
            return False
        selection = selectionPath[0].get_value(selectionPath[1], 0)
        doc = self.docsearch.get_doc(selection)

        self._destroy()

        print "Showing doc %s" % selection
        self.mainwindow.show_doc(doc)

        # XXX(Jflesch): On tilted window managers like Awesome, the main window
        # will only get its final size once this dialog has been fully destroyed
        # and once the main window has been redrawned at least once.
        # And we need the final size of the main window to display the page at the
        # correct scale. So we have to do the following:
        gtk_refresh()
        self.mainwindow.refresh_page()

        return True

    def _connect_signals(self):
        self.searchwin.connect("destroy", lambda x: self._destroy())
        self.searchField.connect("changed", self._update_results)
        self.wTree.get_object("buttonSearchCancel").connect("clicked", lambda x: self._destroy())
        self.wTree.get_object("buttonSearchOk").connect("clicked", lambda x: self._apply())
        self.matchListUI.connect("cursor-changed", self._update_preview)

    def _destroy(self):
        self.wTree.get_object("windowSearch").destroy()


