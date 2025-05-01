import logging

import openpaperwork_core

from openpaperwork_core.interfaces.fs import Fs

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotProvider

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import DocExtraText

from paperwork_gtk.interfaces.doc_properties import DocPropertiesComponent


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    DocPropertiesComponent,
    ScreenshotProvider,
):
    PRIORITY = 750

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocExtraText,
                'defaults': ['paperwork_backend.model.extra_text'],
            },
            {
                "interface": DocStorage,
                "defaults": ["paperwork_backend.model.workdir"],
            },
            {
                "interface": Fs,
                "defaults": ["openpaperwork_gtk.fs.gio"],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': Screenshot,
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.widget_tree = None
        self.active_doc = None

    def _get_widget_text(self):
        text_buffer = self.widget_tree.get_object("doctext_text").get_buffer()
        start = text_buffer.get_iter_at_offset(0)
        end = text_buffer.get_iter_at_offset(-1)
        return text_buffer.get_text(start, end, False)

    def doc_properties_components_get(self, out: list, multiple_docs=False):
        if multiple_docs:
            return
        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docproperties", "extra_text.glade"
        )

        out.append(self.widget_tree.get_object("doctext"))

    def doc_properties_components_set_active_doc(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)
        txt = []
        self.core.call_all(DocExtraText.doc_get_extra_text_by_url, txt, doc_url)
        txt = "\n".join(txt)
        self.widget_tree.get_object("doctext_text").get_buffer().set_text(txt)

    def doc_properties_components_apply_changes(self, out):
        if out.multiple_docs:
            return

        # The document may have been renamed: use out.doc_id instead of
        # self.active_doc
        doc_id = out.doc_id
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)
        self.active_doc = (doc_id, doc_url)

        orig_txt = []
        self.core.call_all(
            DocExtraText.doc_get_extra_text_by_url, orig_txt, doc_url
        )
        orig_txt = "\n".join(orig_txt).strip()

        new_txt = self._get_widget_text()

        if new_txt == orig_txt:
            return

        LOGGER.info("Extra keywords have been changed in document %s", doc_id)
        self.core.call_all(
            DocExtraText.doc_set_extra_text_by_url, doc_url, new_txt
        )

        out.upd_docs.add(doc_id)

    def doc_properties_components_cancel_changes(self):
        self.doc_properties_components_set_active_doc(*self.active_doc)

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.widget_tree.get_object("doctext_text"),
            self.core.call_success(
                Fs.fs_join, out_dir, "doc_extra_text.png"
            ),
            margins=(50, 50, 50, 50)
        )

    @openpaperwork_core.noop
    def doc_properties_components_set_active_docs(self, doc_id, doc_url):
        pass
