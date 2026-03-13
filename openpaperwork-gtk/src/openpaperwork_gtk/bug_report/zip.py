import logging
import re
import zipfile

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core

from openpaperwork_gtk.interfaces.bug_report import GtkBugReportBuilder
from openpaperwork_gtk.interfaces.bug_report import GtkBugReportDisplay
from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk import (_, deps)


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    GtkBugReportBuilder,
):
    PRIORITY = -100

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_gtk.fs.gio'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkBugReportDisplay,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.widget_tree = None
        self.file_urls = []
        self.apply_handler_id = None

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(deps.GTK)

    def build_gtk_bug_report(self, *args):
        url = "https://gitlab.gnome.org/World/OpenPaperwork/paperwork/issues"
        self.core.call_all(
            GtkBugReportDisplay.bug_report_add_method,
            _("ZIP file"),
            re.sub(
                '[ \t]+', ' ',
                (
                    _(
                        "Build a ZIP file containing all the attachments.\n"
                        " If you want, you can then submit a bug report"
                        ' manually on <a href="%s">Paperwork\'s bug'
                        " tracker</a> and attach this ZIP file to the ticket."
                    ) % url
                ).strip()
            ),
            self._enable_zip, self._disable_zip,
            *args
        )

    def _enable_zip(self, bug_report_widget_tree):
        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "openpaperwork_gtk.bug_report", "bug_report_zip.glade"
        )

        assistant = bug_report_widget_tree.get_object("bug_report_dialog")
        page = self.widget_tree.get_object("bug_report_zip_page")
        assistant.append_page(page)
        assistant.set_page_complete(page, False)
        assistant.set_page_type(page, Gtk.AssistantPageType.CONFIRM)
        self.apply_handler_id = assistant.connect("apply", self._make_zip)

        filechooser = self.widget_tree.get_object("bug_report_zip_filechooser")
        filechooser.connect(
            "selection-changed",
            lambda filechooser: assistant.set_page_complete(
                page, filechooser.get_uri() is not None
            )
        )

    def _disable_zip(self, bug_report_widget_tree):
        if self.widget_tree is None:
            return
        assistant = bug_report_widget_tree.get_object("bug_report_dialog")
        page = self.widget_tree.get_object("bug_report_zip_page")
        assistant.remove(page)
        assistant.disconnect(self.apply_handler_id)
        self.widget_tree = None

    def bug_report_set_file_urls_to_send(self, file_urls):
        self.file_urls = file_urls

    def _make_zip(self, assistant):
        in_file_urls = self.file_urls
        out_file_url = self.widget_tree.get_object(
            "bug_report_zip_filechooser"
        ).get_uri()
        out_file_url = out_file_url.strip()
        if not out_file_url.lower().endswith(".zip"):
            out_file_url += ".zip"
        LOGGER.info("Adding attachments to %s", out_file_url)

        out_file_path = self.core.call_success(Fs.fs_unsafe, out_file_url)
        with zipfile.ZipFile(out_file_path, 'w') as out_zip:
            for in_file_url in in_file_urls:
                file_name = self.core.call_success(Fs.fs_basename, in_file_url)
                with self.core.call_success(
                        Fs.fs_open, in_file_url, "rb") as in_fd:
                    with out_zip.open(file_name, 'w') as out_fd:
                        out_fd.write(in_fd.read())

        LOGGER.info("%s written", out_file_url)
