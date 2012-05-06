import os
import threading

import gtk
import gettext
import gobject

from paperwork.controller.actions import connect_buttons
from paperwork.controller.actions import do_actions
from paperwork.controller.actions import SimpleAction
from paperwork.controller.workers import Worker
from paperwork.model.doc import ScannedDoc
from paperwork.model.docsearch import DummyDocSearch
from paperwork.model.docsearch import DocSearch
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile

_ = gettext.gettext


class WorkerDocIndexer(Worker):
    """
    Reindex all the documents
    """

    __gsignals__ = {
        'indexation-start' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'indexation-progression' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                                    (gobject.TYPE_FLOAT, gobject.TYPE_STRING)),
        'indexation-end' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    can_interrupt = True

    def __init__(self, main_window, config):
        Worker.__init__(self, "Document reindexation")
        self.__main_win = main_window
        self.__config = config

    def __cb_progress(self, progression, total, step, doc=None):
        """
        Update the main progress bar
        """
        txt = None
        if step == DocSearch.INDEX_STEP_READING:
            txt = _('Reading ...')
        elif step == DocSearch.INDEX_STEP_SORTING:
            txt = _('Sorting ...')
        else:
            assert()  # unknown progression type
            txt = ""
        if doc != None:
            txt += (" (%s)" % (doc.name))
        self.emit('indexation-progression', float(progression) / total, txt)
        if not self.can_run:
            raise StopIteration()

    def do(self):
        self.emit('indexation-start')
        try:
            docsearch = DocSearch(self.__config.workdir, self.__cb_progress)
            self.__main_win.docsearch = docsearch
        except StopIteration:
            print "Indexation interrupted"
        self.emit('indexation-end')

gobject.type_register(WorkerDocIndexer)


class ActionNewDocument(SimpleAction):
    """
    Starts a new document.
    Warning: Won't change anything in the UI
    """
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "New document")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        self.__main_win.doc = ScannedDoc(self.__config.workdir)


class ActionStartWorker(SimpleAction):
    """
    Start a threaded job
    """
    def __init__(self, worker):
        SimpleAction.__init__(self, str(worker))
        self.__worker = worker

    def do(self):
        SimpleAction.do(self)
        self.__worker.start()


class ActionUpdateSearchResults(SimpleAction):
    """
    Update search results
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Update search results")
        self.__main_win = main_window
    
    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_doc_list()


class ActionQuit(SimpleAction):
    """
    Quit
    """
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Quit")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)

        for worker in self.__main_win.workers.values():
            if worker.is_running and not worker.can_interrupt:
                print ("Sorry, can't quit. Another thread is still running and"
                       " can't be interrupted")
                return
        for worker in self.__main_win.workers.values():
            if worker.is_running:
                worker.stop()

        self.__main_win.window.destroy()
        gtk.main_quit()


class MainWindow(object):
    def __init__(self, config):
        widget_tree = load_uifile("mainwindow.glade")

        self.window = widget_tree.get_object("mainWindow")

        self.docsearch = DummyDocSearch()
        self.doc = None

        self.listStores = {
            'suggestions' : widget_tree.get_object("liststoreSuggestion"),
            'labels' : widget_tree.get_object("liststoreLabel"),
            'matches' : widget_tree.get_object("liststoreMatch"),
            'pages' : widget_tree.get_object("liststorePage"),
            'zoomLevels' : widget_tree.get_object("liststoreZoom"),
        }

        self.indicators = {
            'total_pages' : widget_tree.get_object("labelTotalPages"),
        }

        self.search_field = widget_tree.get_object("entrySearch")

        self.doc_browsing = {
            'matches' : widget_tree.get_object("treeviewMatch"),
            'pages' : widget_tree.get_object("iconviewPage"),
            'labels' : widget_tree.get_object("treeviewLabel"),
            'search' : self.search_field,
        }

        self.text_area = widget_tree.get_object("textviewPageTxt")
        self.img_area = widget_tree.get_object("imagePageImg")

        self.status = {
            'progress' : widget_tree.get_object("progressbar"),
            'text' : widget_tree.get_object("statusbar"),
        }

        self.popupMenus = {
            'labels' : (
                widget_tree.get_object("treeviewLabel"),
                widget_tree.get_object("popupmenuLabels")
            ),
            'matches' : (
                widget_tree.get_object("treeviewMatch"),
                widget_tree.get_object("popupmenuMatchs")
            ),
            'pages' : (
                widget_tree.get_object("iconviewPage"),
                widget_tree.get_object("popupmenuPages")
            )
        }

        self.workers = {
            'reindex' : WorkerDocIndexer(self, config)
        }

        self.actions = {
            # Basic actions: there should be at least 2 items to do each of
            # them
            'new_doc' : (
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
                widget_tree.get_object("toolbuttonPrevPage"),
                # the second way of doing that is clicking in the page list
            ],
            'next_page' : [
                widget_tree.get_object("toolbuttonNextPage"),
                # the second way of doing that is clicking in the page list
            ],
            'current_page' : [
                widget_tree.get_object("entryPageNb"),
                # the second way of selecting a page is clicking in the page
                # list
            ],
            'zoom_levels' : [
                widget_tree.get_object("comboboxZoom"),
                # TODO
            ],
            'search' : (
                [
                    self.search_field,
                    # 2 search fields wouldn't make sense
                ],
                [
                    ActionUpdateSearchResults(self),
                ]
            ),

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
            'reindex' : (
                [
                    widget_tree.get_object("menuitemReindexAll"),
                ],
                [
                    ActionStartWorker(self.workers['reindex'])
                ],
            ),
            'about' : [
                widget_tree.get_object("menuitemAbout"),
            ],
        }

        connect_buttons(self.actions['new_doc'][0], self.actions['new_doc'][1])
        connect_buttons(self.actions['reindex'][0], self.actions['reindex'][1])
        connect_buttons(self.actions['quit'][0], self.actions['quit'][1])
        connect_buttons(self.actions['search'][0], self.actions['search'][1])

        self.workers['reindex'].connect('indexation-start', lambda indexer: \
                                        self.set_progression(self.workers['reindex'],
                                                            0.0, None))
        self.workers['reindex'].connect('indexation-start', lambda indexer: \
                                        self.set_search_availability(False))
        self.workers['reindex'].connect('indexation-start', lambda indexer: \
                                        self.set_mouse_cursor("Busy"))
        self.workers['reindex'].connect('indexation-progression',
                                        self.set_progression)

        self.workers['reindex'].connect('indexation-end', lambda indexer: \
                                        self.set_search_availability(True))
        self.workers['reindex'].connect('indexation-end', lambda indexer: \
                                        self.set_mouse_cursor("Normal"))
        self.workers['reindex'].connect('indexation-end', lambda indexer: \
                                        self.set_progression(self.workers['reindex'],
                                                            0.0, None))
        self.workers['reindex'].connect('indexation-end', lambda indexer: \
                                        self.refresh_page_list())
        self.workers['reindex'].connect('indexation-end', lambda indexer: \
                                        self.refresh_doc_list())
        self.workers['reindex'].connect('indexation-end', lambda indexer: \
                                        self.refresh_label_list())

        self.window.set_visible(True)

    def set_search_availability(self, enabled):
        print "Change search availability: %s" % str(enabled)
        for list_view in self.doc_browsing.values():
            list_view.set_sensitive(enabled)

    def set_mouse_cursor(self, cursor):
        self.window.window.set_cursor({
            "Normal" : None,
            "Busy" : gtk.gdk.Cursor(gtk.gdk.WATCH),
        }[cursor])

    def set_progression(self, src, progression, text):
        context_id = self.status['text'].get_context_id(str(src))
        self.status['text'].pop(context_id)
        if (text != None and text != ""):
            self.status['text'].push(context_id, text)
        self.status['progress'].set_fraction(progression)

    def refresh_doc_list(self):
        """
        Update the suggestions list and the matching documents list based on
        the keywords typed by the user in the search field.
        """
        sentence = unicode(self.search_field.get_text())
        print "Search: %s" % (sentence.encode('ascii', 'replace'))

        suggestions = self.docsearch.find_suggestions(sentence)
        print "Got %d suggestions" % len(suggestions)
        self.listStores['suggestions'].clear()
        for suggestion in suggestions:
            self.listStores['suggestions'].append([suggestion])

        documents = self.docsearch.find_documents(sentence)
        print "Got %d documents" % len(documents)
        documents = reversed(documents)

        self.listStores['matches'].clear()
        for doc in documents:
            labels = doc.labels
            final_str = doc.name
            nb_pages = doc.nb_pages
            if nb_pages > 1:
                final_str += (_("\n  %d pages") % (doc.nb_pages))
            if len(labels) > 0:
                final_str += ("\n  "
                        + "\n  ".join([x.get_html() for x in labels]))
            self.listStores['matches'].append([final_str, doc])

    def refresh_page_list(self):
        """
        Reload and refresh the page list
        """
        self.listStores['pages'].clear()
        for page in self.doc.pages:
            img = page.get_thumbnail(150)
            pixbuf = image2pixbuf(img)
            self.listStores['pages'].append([
                pixbuf, _('Page %d') % (page.page_nb + 1),
                page.page_nb
            ])
        self.indicators['total_pages'].set_text(
                _("/ %d") % (self.__main_win.doc.nb_pages))

    def refresh_label_list(self):
        """
        Reload and refresh the label list
        """
        self.listStores['labels'].clear()
        labels = self.doc.labels
        for label in self.docsearch.label_list:
            self.listStores['labels'].append([
                label.get_html(),
                (label in labels),
                label
            ])
