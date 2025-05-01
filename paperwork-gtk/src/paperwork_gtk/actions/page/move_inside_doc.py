import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False
try:
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.dialogs import GtkSingleEntryDialog
from openpaperwork_gtk.interfaces.dialogs import GtkSingleEntryDialogListener
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
import openpaperwork_gtk
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.pages import PageManagement

from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.app_actions import AppActionCollector
from paperwork_gtk.interfaces.doc_viewer import PageViewerListener
from paperwork_gtk import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_move_inside_doc"


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    DocOpener,
    PageViewerListener,
    GtkSingleEntryDialogListener,
    GtkWindowListener,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': AppActionCollector,
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
            {
                'interface': PageManagement,
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.img_overlay',
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': GtkSingleEntryDialog,
                'defaults': ['openpaperwork_gtk.dialogs.single_entry'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        self.active_doc = None
        self.active_page_idx = -1
        self.windows = []

        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._start_move_inside_doc)
        self.core.call_all(AppActionCollector.app_actions_add, action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def doc_close(self):
        self.active_doc = None

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _show_error(self, msg):
        flags = (
            Gtk.DialogFlags.MODAL |
            Gtk.DialogFlags.DESTROY_WITH_PARENT
        )
        dialog = Gtk.MessageDialog(
            transient_for=self.windows[-1],
            flags=flags,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=msg
        )
        dialog.connect("response", lambda dialog, response: dialog.destroy())
        dialog.show_all()

    def _start_move_inside_doc(self, *args, **kwargs):
        assert self.active_doc is not None
        assert self.active_page_idx is not None
        msg = _("Move the page %d to what position ?") % (
            self.active_page_idx + 1
        )
        self.core.call_success(
            GtkSingleEntryDialog.gtk_show_dialog_single_entry,
            self, msg, str(self.active_page_idx + 1),
            active_doc=self.active_doc,
            active_page_idx=self.active_page_idx
        )

    def on_dialog_single_entry_reply(
            self, origin, r, new_position, *args, **kwargs):
        if origin is not self:
            return None
        if not r:
            return None
        try:
            new_position = int(new_position) - 1
        except ValueError:
            self._show_error(_("Invalid page position: %s") % (new_position))
            return True

        active_doc = kwargs['active_doc']
        active_page_idx = kwargs['active_page_idx']

        nb_pages = self.core.call_success(
            Docs.doc_get_nb_pages_by_url, active_doc[1]
        )
        if new_position >= nb_pages or new_position < 0:
            self._show_error(
                _(
                    "Invalid page position: %d."
                    " Out of document bounds (1-%d)."
                ) % (
                    new_position,
                    nb_pages
                )
            )
            return True
        if new_position == active_page_idx:
            self._show_error(_("Page position unchanged"))
            return True

        promise = openpaperwork_core.promise.Promise(self.core)
        promise = promise.then(
            self.core.call_all,
            PageManagement.page_move_by_url,
            active_doc[1], active_page_idx,
            active_doc[1], new_position
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_all, DocOpener.doc_reload, *active_doc
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_success(
            DocTransactionManager.transaction_simple_promise,
            [('upd', active_doc[0])]
        ))
        self.core.call_success(DocTransactionManager.transaction_schedule, promise)

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
