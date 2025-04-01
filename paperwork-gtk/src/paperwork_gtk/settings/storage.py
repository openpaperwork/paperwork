import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_gtk.deps

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000000

    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'gtk_settings',
            'gtk_window_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.windows = []
        self.workdir = self.core.call_success("config_get", "workdir")

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _show_workdir_info(self, *args, **kwargs):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings", "storage.glade"
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
            "gtk_load_widget_tree", "paperwork_gtk.settings", "storage.glade"
        )

        workdir_button = widget_tree.get_object("work_dir_chooser_button")
        basename = self.core.call_success("fs_basename", self.workdir)
        workdir_button.set_label(basename)
        workdir_button.connect("clicked", self._on_button_clicked, widget_tree)

        workdir_info_button = widget_tree.get_object("button_workdir_info")
        workdir_info_button.connect("clicked", self._show_workdir_info)

        self.core.call_success(
            "add_setting_to_dialog", global_widget_tree, _("Storage"),
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
        workdir = self.core.call_success("config_get", "workdir")
        if self.core.call_success("fs_exists", workdir):
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
        self.core.call_all("config_put", "workdir", workdir)

        # Bug report 170: Make sure the current document (in the old work
        # directory) is closed so the user cannot use it by accident anymore
        self.core.call_all("doc_close")

        basename = self.core.call_success("fs_basename", workdir)
        widget_tree.get_object("work_dir_chooser_button").set_label(basename)

        # Basic check of work directory content to avoid common mistake.
        # We do not prevent the user from selecting the folder. We just
        # warn them.
        workdir_content = self.core.call_success("fs_listdir", workdir)
        show_info_dialog = False
        for file_url in workdir_content:
            file_name = self.core.call_success("fs_basename", file_url)
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

    def config_save(self):
        workdir = self.core.call_success("config_get", "workdir")

        if workdir != self.workdir:
            LOGGER.info("Work directory has been changed --> Synchronizing")
            self.core.call_all("transaction_sync_all")

        self.workdir = workdir
