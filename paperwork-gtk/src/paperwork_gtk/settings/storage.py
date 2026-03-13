import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.work_queue import WorkQueue
from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core
import openpaperwork_core.deps

import openpaperwork_gtk.deps
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import DocOpener
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager

from paperwork_gtk import _
from paperwork_gtk.interfaces.settings_dialog import SettingsDialog
from paperwork_gtk.interfaces.settings_dialog import SettingsDialogComponent


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    GtkWindowListener,
    SettingsDialogComponent,
):
    PRIORITY = 10000000

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Config,
                defaults=["openpaperwork_core.config"],
            ),
            openpaperwork_core.Dependency(
                interface=DocOpener,
                defaults=[],
            ),
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=DocTransactionManager,
                defaults=[],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_gtk.fs.gio'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=SettingsDialog,
                defaults=["paperwork_gtk.settings"],
            ),
            openpaperwork_core.Dependency(
                interface=WorkQueue,
                defaults=['paperwork_backend.sync'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.windows = []
        self.workdir = self.core.call_success(Config.config_get, "workdir")
        self.core.call_all(Config.config_add_observer, "workdir", self._on_workdir_changed)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _show_workdir_info(self, *args, **kwargs):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree, "paperwork_gtk.settings", "storage.glade"
        )
        dialog = widget_tree.get_object("workdir_info_dialog")
        dialog.set_transient_for(self.windows[-1])
        dialog.set_modal(True)
        dialog.connect("response", self._on_workdir_info_dialog_closed)
        dialog.connect("destroy", self._on_workdir_info_dialog_closed)
        dialog.set_visible(True)

    def _on_workdir_info_dialog_closed(self, dialog, *args, **kwargs):
        dialog.set_visible(False)

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree, "paperwork_gtk.settings", "storage.glade"
        )

        workdir_button = widget_tree.get_object("work_dir_chooser_button")
        basename = self.core.call_success(Fs.fs_basename, self.workdir)
        workdir_button.set_label(basename)
        workdir_button.connect("clicked", self._on_button_clicked, widget_tree)

        workdir_info_button = widget_tree.get_object("button_workdir_info")
        workdir_info_button.connect("clicked", self._show_workdir_info)

        self.core.call_success(
            SettingsDialog.add_setting_to_dialog, global_widget_tree, _("Storage"),
            [widget_tree.get_object("workdir")],
            extra_widget=workdir_info_button,
        )

    def _on_button_clicked(self, button, widget_tree):
        dialog = Gtk.FileChooserDialog(
            _("Work Directory"),
            self.windows[-1],
            Gtk.FileChooserAction.SELECT_FOLDER,
            (
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT
            )
        )
        dialog.set_modal(True)
        dialog.set_local_only(False)
        workdir = self.core.call_success(Config.config_get, "workdir")
        if self.core.call_success(Fs.fs_exists, workdir):
            dialog.set_uri(workdir)
        dialog.connect("response", self._on_file_dialog_response, widget_tree)
        dialog.show_all()

    def _on_file_dialog_response(self, dialog, response_id, widget_tree):
        if (response_id != Gtk.ResponseType.ACCEPT and
                response_id != Gtk.ResponseType.OK and
                response_id != Gtk.ResponseType.YES and
                response_id != Gtk.ResponseType.APPLY):
            LOGGER.info("User canceled (response_id=%d)", response_id)
            dialog.destroy()
            return

        workdir = dialog.get_uri()
        dialog.set_visible(False)

        LOGGER.info("Setting work directory to %s", workdir)
        self.core.call_all(Config.config_put, "workdir", workdir)

        # Bug report 170: Make sure the current document (in the old work
        # directory) is closed so the user cannot use it by accident anymore
        self.core.call_all(DocOpener.doc_close)

        basename = self.core.call_success(Fs.fs_basename, workdir)
        widget_tree.get_object("work_dir_chooser_button").set_label(basename)

        # Basic check of work directory content to avoid common mistake.
        # We do not prevent the user from selecting the folder. We just
        # warn them.
        workdir_content = self.core.call_success(Fs.fs_listdir, workdir)
        show_info_dialog = False
        for file_url in workdir_content:
            file_name = self.core.call_success(Fs.fs_basename, file_url)
            if file_name[0] == ".":
                continue
            if "." in file_name:
                # assume it's a file ; anyway, it doesn't have the usual
                # name format that Paperwork folders have
                LOGGER.warning(
                    "Suspect file name found in work directory: %s",
                    file_name
                )
                show_info_dialog = True
                break
        if show_info_dialog:
            self._show_workdir_info()

    def _on_workdir_changed(self):
        workdir = self.core.call_success(Config.config_get, "workdir")

        if workdir != self.workdir:
            LOGGER.info("Work directory has been changed --> Synchronizing")
            self.core.call_all(DocTransactionManager.transaction_sync_all)

        self.workdir = workdir

    @openpaperwork_core.noop
    def on_settings_closed(self, settings_dialog_widget_tree):
        pass
