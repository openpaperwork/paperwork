import gettext
import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps

import paperwork_backend.docimport

from . import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc_id = None
        self.windows = []

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_open',
            'gtk_doc_import',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_dialog_single_entry',
                'defaults': ['openpaperwork_gtk.dialogs.single_entry'],
            },
            {
                'interface': 'import',
                'defaults': [
                    'paperwork_backend.docimport.img',
                    'paperwork_backend.docimport.pdf',
                ],
            },
            {
                'interface': 'notifications',
                'defaults': ['paperwork_gtk.notifications.dialog'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def doc_open(self, doc_id, doc_url):
        if self.core.call_success("is_doc", doc_url) is None:
            # New document --> no need to track this doc id.
            # Importer will create a new document in time
            self.active_doc_id = None
            return
        self.active_doc_id = doc_id

    def doc_close(self):
        self.active_doc_id = None

    def _show_no_importer(self, file_uris):
        msg = (
            _("Don't know how to import '%s'. Sorry.") % (file_uris)
        )
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

    def _request_password(self, importer, file_import):
        self.core.call_success(
            "gtk_show_dialog_single_entry", self,
            _("PDF password"), "",
            importer=importer, file_import=file_import
        )

    def on_dialog_single_entry_reply(
            self, origin, reply, password, *args, **kwargs):
        if origin != self:
            # Not ours
            return
        if not reply:
            # User cancelled
            return
        importer = kwargs['importer']
        file_import = kwargs['file_import']
        self._do_import(importer, file_import, data={'password': password})
        return True

    def _show_result_no_doc(self):
        msg = _("No new document to import found")
        flags = (
            Gtk.DialogFlags.MODAL |
            Gtk.DialogFlags.DESTROY_WITH_PARENT
        )
        dialog = Gtk.MessageDialog(
            transient_for=self.windows[-1],
            flags=flags,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=msg
        )
        dialog.connect(
            "response", lambda dialog, response: dialog.destroy()
        )
        dialog.show_all()

    def _show_result_doc(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        assert doc_url is not None

        if self.active_doc_id != doc_id:
            self.core.call_all("doc_open", doc_id, doc_url)

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            # may happen with freshly-import .doc/.xsl/.docx/etc files
            nb_pages = 0
        if nb_pages <= 0:
            # empty PDF ?
            LOGGER.warning("Document import %s, but no page in it yet ?!", doc_id)
            return
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "doc_goto_page", nb_pages - 1
        )

    def _delete_files(self, file_uris):
        LOGGER.info("Moving imported file(s) to trash ...")
        for file_uri in file_uris:
            LOGGER.info("Moving %s to trash ...", file_uri)
            self.core.call_success("fs_unlink", file_uri)
        notification = self.core.call_success(
            "get_notification_builder",
            gettext.npgettext(
                "import dialog",
                "Imported file deleted",
                "Imported files deleted",
                len(file_uris)
            ),
        )
        if notification is None:
            return
        notification.set_icon("edit-delete").show()

    def _show_result_notification(self, file_import):
        msg = _("Imported:\n")
        for (k, v) in file_import.stats.items():
            msg += ("- {}: {}\n".format(k, v))
        msg = msg.strip()

        notification = self.core.call_success(
            "get_notification_builder", _("Import successful"),
            need_actions=True
        )
        if notification is not None:
            notification.set_message(
                msg
            ).set_icon(
                "document-new"
            ).add_action(
                "delete", _("Delete imported files"),
                self._delete_files, file_import.imported_files
            ).show()

    def _show_result(self, file_import):
        doc_id = None
        if len(file_import.upd_doc_ids) > 0:
            doc_id = list(file_import.upd_doc_ids)[0]
        if len(file_import.new_doc_ids) > 0:
            doc_id = list(file_import.new_doc_ids)[0]
        if doc_id is None:
            self._show_result_no_doc()
            return
        self._show_result_doc(doc_id)
        self._show_result_notification(file_import)

    def _reload_docs(self, file_import):
        for doc_id in file_import.upd_doc_ids:
            doc_url = self.core.call_success("doc_id_to_url", doc_id)
            self.core.call_all("doc_reload", doc_id, doc_url)

    def _add_to_recent(self, file_uris):
        for file_uri in file_uris:
            if self.core.call_success("fs_isdir", file_uri) is None:
                # If the user imported a file, assume they won't import it
                # twice but they may import again other files from the same
                # directory
                file_uri = self.core.call_success("fs_dirname", file_uri)
            LOGGER.info("Adding %s to recently used files", file_uri)
            Gtk.RecentManager().add_item(file_uri)

    def _log_result(self, file_import):
        LOGGER.info("Import result:")
        LOGGER.info("- Imported files: %s", file_import.imported_files)
        LOGGER.info("- Non-imported files: %s", file_import.ignored_files)
        LOGGER.info("- New documents: %s", file_import.new_doc_ids)
        LOGGER.info("- Updated documents: %s", file_import.upd_doc_ids)
        for (k, v) in file_import.stats.items():
            LOGGER.info("- %s: %s", k, v)

    def _do_import(self, importer, file_import, data=None):
        promise = importer.get_import_promise(data)
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self._log_result, file_import)
        promise = promise.then(self._show_result, file_import)
        promise = promise.then(self._reload_docs, file_import)
        self.core.call_success("transaction_schedule", promise)

    def gtk_doc_import(self, file_urls):
        LOGGER.info("Importing: %s", file_urls)

        file_import = paperwork_backend.docimport.FileImport(
            file_urls, self.active_doc_id
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        if len(importers) <= 0:
            self._show_no_importer(file_urls)
            return
        # TODO(Jflesch): Should ask the user what must be done if many
        # importers are possible.
        importer = importers[0]

        self._add_to_recent(file_urls)

        required = set()
        for (k, v) in importer.get_required_data().items():
            required.update(v)

        LOGGER.info(
            "Required data to import %s: %s",
            file_urls, required
        )
        if "password" in required:
            self._request_password(importer, file_import)
        else:
            self._do_import(importer, file_import)
        return True
