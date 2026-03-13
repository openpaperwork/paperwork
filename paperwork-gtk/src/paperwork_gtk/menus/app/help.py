from typing import Optional
import logging

from paperwork_gtk.interfaces.app_menu import AppMenu

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_gtk import _
from paperwork_gtk.interfaces.app_actions import AppAction
from paperwork_gtk.interfaces.doc_list import DocListListener
from paperwork_gtk.interfaces.help import HelpDocs
from paperwork_gtk.interfaces.help import HelpMenu

LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    AppAction,
    Chkdeps,
    DocListListener,
    HelpMenu,
):
    PRIORITY = -1000

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=HelpDocs,
                defaults=['paperwork_gtk.model.help'],
            ),
            openpaperwork_core.Dependency(
                interface=AppMenu,
                defaults=['paperwork_gtk.mainwindow.doclist'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.menu: Optional[Gio.Menu] = None
        if not GIO_AVAILABLE:
            return
        self.menu = Gio.Menu()

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        for (title, file_name) in self.core.call_success(HelpDocs.help_get_files):
            item = Gio.MenuItem.new(title, "win.open_help." + file_name)
            self.menu.append_item(item)
        self.core.call_all(AppMenu.menu_app_append_submenu, _("Help"), self.menu)

    def help_add_menu_item(self, menu_item):
        self.menu.append_item(menu_item)

    @openpaperwork_core.noop
    def on_doc_list_clear(self):
        pass

    @openpaperwork_core.noop
    def on_doc_box_creation(self, doc_id, row, flowlayout):
        pass

    @openpaperwork_core.noop
    def on_doc_list_visibility_changed(self):
        pass

    @openpaperwork_core.noop
    def on_doc_box_visible(self, doc_id, gtk_row, layout):
        pass
