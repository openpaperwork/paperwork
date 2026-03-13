import logging

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.external_apps import ExternalApps
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.screenshot import (
    Screenshot,
    ScreenshotProvider
)

from paperwork_backend.interfaces.doc_converted import DocConverted
from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk.interfaces.doc_viewer import (
    PageInfo,
    PageMenu,
    PageMenuListener,
    PageViewerListener
)
from paperwork_gtk.interfaces.page_editor import PageEditor

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocOpener,
    PageViewerListener,
    PageMenu,
    ScreenshotProvider,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocConverted,
                defaults=[],
            ),
            openpaperwork_core.Dependency(
                interface=ExternalApps,
                defaults=['openpaperwork_core.external_apps.xdg'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_gtk.fs.gio"],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=["openpaperwork_gtk.mainloop.glib"],
            ),
            openpaperwork_core.Dependency(
                interface=PageEditor,
                defaults=['paperwork_gtk.mainwindow.pageeditor'],
            ),
            openpaperwork_core.Dependency(
                interface=PageInfo,
                defaults=['paperwork_gtk.mainwindow.docview.pageinfo'],
            ),
            openpaperwork_core.Dependency(
                interface=PageMenuListener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=Screenshot,
                defaults=['openpaperwork_gtk.screenshots'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = None
        self.active_page = None
        self.button_edit = None

        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docview.pageinfo",
            "actions.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.menu_model = self.widget_tree.get_object("page_menu_model")
        self.submenus = {}

        self.button_edit = self.widget_tree.get_object("page_action_edit")
        self.button_edit.connect(
            "clicked", self._on_edit
        )

        self.core.call_success(
            PageInfo.page_info_add_right, self.widget_tree.get_object("page_actions")
        )

        self.core.call_success(
            Mainloop.mainloop_schedule, self.core.call_all,
            PageMenuListener.on_page_menu_ready
        )

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    @openpaperwork_core.noop
    def doc_close(self):
        pass

    def on_page_shown(self, page_idx):
        self.active_page = page_idx

    def _on_edit(self, button):
        doc_url = self.active_doc[1]
        converted_info = self.core.call_success(DocConverted.doc_is_converted, doc_url)
        if converted_info is not None:
            original_doc_url = converted_info[0]
            self.core.call_success(ExternalApps.external_app_open_file, original_doc_url)
        else:
            self.core.call_all(
                PageEditor.gtk_open_page_editor, *self.active_doc, self.active_page
            )

    def page_menu_open(self):
        self.widget_tree.get_object("page_actions_other").clicked()

    def page_menu_append_item(self, item, submenu_name=None):
        menu = self.menu_model
        if submenu_name is not None:
            menu = self.submenus.get(submenu_name, None)
            if menu is None:
                menu = Gio.Menu()
                self.submenus[submenu_name] = menu
                self.menu_model.append_submenu(submenu_name, menu)
        menu.append_item(item)

    def screenshot_snap_all_doc_widgets(self, out_dir):
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("page_actions"),
            self.core.call_success(Fs.fs_join, out_dir, "page_actions.png"),
            margins=(50, 50, 50, 50)
        )

    def screenshot_snap_page_action_menu(self, out_file):
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("page_actions"),
            out_file,
            margins=(50, 200, 50, 50)
        )

    @openpaperwork_core.noop
    def on_page_size_obtained(self, page):
        pass
