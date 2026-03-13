import logging
import random

from paperwork_gtk.interfaces.notifications import Notifications

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    GI_AVAILABLE = False

try:
    GTK_AVAILABLE = False
    if GI_AVAILABLE:
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        GTK_AVAILABLE = True
except (ImportError, ValueError):
    pass


from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.doc_import import ImporterFactory

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_import import DocImport
from paperwork_gtk.interfaces.page_add import PageAddButtons
from paperwork_gtk.interfaces.page_add import PageAddButtonsSources


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    GtkWindowListener,
    PageAddButtonsSources,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Config,
                defaults=["openpaperwork_core.config"],
            ),
            openpaperwork_core.Dependency(
                interface=DocImport,
                defaults=['paperwork_gtk.docimport'],
            ),
            openpaperwork_core.Dependency(
                interface=ImporterFactory,
                defaults=[
                    'paperwork_backend.docimport.img',
                    'paperwork_backend.docimport.pdf',
                ],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=["openpaperwork_gtk.mainloop.glib"],
            ),
            openpaperwork_core.Dependency(
                interface=Notifications,
                defaults=["paperwork_gtk.notifications.dialog"],
            ),
            openpaperwork_core.Dependency(
                interface=PageAddButtons,
                defaults=['paperwork_gtk.mainwindow.docview.pageadd.source_popover'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.widget_tree = None
        self.windows = []

        if not GTK_AVAILABLE:
            return
        opt = self.core.call_success(
            Config.config_build_simple, "GUI", "last_import_uri",
            lambda: None
        )
        self.core.call_all(Config.config_register, "last_import_uri", opt)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def pageadd_get_sources(self, out: list):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docview.pageadd", "source_box.glade"
        )
        source_long_txt = _("Import document or image file(s)")
        source_short_txt = _("Import file(s)")
        img = "insert-image-symbolic"

        widget_tree.get_object("source_image").set_from_icon_name(
            img, Gtk.IconSize.SMALL_TOOLBAR
        )
        widget_tree.get_object("source_name").set_text(source_long_txt)

        out.append(
            (
                widget_tree.get_object("source_selector"),
                source_short_txt, "import", self._on_import
            )
        )

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _on_import(self, doc_id, doc_url, source_id):
        LOGGER.info("Opening file chooser dialog")

        mimes = set()
        self.core.call_all(ImporterFactory.get_import_mime_types, mimes)
        mimes = list(mimes)
        mimes.sort()

        dialog = Gtk.FileChooserDialog(
            _("Select a file or a directory to import"),
            self.windows[-1],
            Gtk.FileChooserAction.OPEN,
            (
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                # WORKAROUND(Jflesch): Use response ID 0 so the user
                # can select a folder.
                Gtk.STOCK_OPEN, 0
            )
        )
        dialog.set_select_multiple(True)
        dialog.set_local_only(False)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("All supported file formats"))
        for (txt, mime) in mimes:
            filter_all.add_mime_type(mime)
        dialog.add_filter(filter_all)

        file_filter = Gtk.FileFilter()
        file_filter.set_name(_("Any files"))
        file_filter.add_pattern("*.*")
        dialog.add_filter(file_filter)

        for (txt, mime) in mimes:
            file_filter = Gtk.FileFilter()
            file_filter.add_mime_type(mime)
            file_filter.set_name(txt)
            dialog.add_filter(file_filter)

        dialog.set_filter(filter_all)

        last_import_uri = self.core.call_success(
            Config.config_get, "last_import_uri"
        )
        if last_import_uri is not None:
            # this filename does not exist, but the parent directory
            # will be selected. A hack inspired by what firefox does.
            dialog.set_uri(last_import_uri + str(random.randint(0, 10000)))
        dialog.connect("response", self._on_dialog_response)

        self.core.call_all(PageAddButtons.pageadd_busy_add)

        dialog.show_all()

    def _on_dialog_response(self, dialog, response_id):
        self.core.call_all(PageAddButtons.pageadd_busy_remove)

        if (response_id != 0 and
                response_id != Gtk.ResponseType.ACCEPT and
                response_id != Gtk.ResponseType.OK and
                response_id != Gtk.ResponseType.YES and
                response_id != Gtk.ResponseType.APPLY):
            LOGGER.info("User canceled (response_id=%d)", response_id)
            dialog.destroy()
            return

        selected = dialog.get_uris()

        dialog.destroy()

        if len(selected) <= 0:
            notif = self.core.call_success(
                Notifications.get_notification_builder,
                _("Nothing to import")
            )
            notif.set_message(_("Nothing to import: nothing selected"))
            notif.set_icon("dialog-error")
            notif.show()
            return

        self.core.call_all(Config.config_put, "last_import_uri", selected[0])

        self.core.call_all(DocImport.gtk_doc_import, selected)
