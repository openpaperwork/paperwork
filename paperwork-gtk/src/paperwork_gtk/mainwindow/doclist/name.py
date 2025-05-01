import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.i18n import I18n
import openpaperwork_core
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import DocType

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_list import DocListListener


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocListListener,
):
    PRIORITY = 1000

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocStorage,
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                "interface": DocType,
                "defaults": [
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ],
            },
            {
                'interface': I18n,
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_doc_box_creation(self, doc_id, gtk_row, custom_flowlayout):
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)
        is_new = doc_url is None or self.core.call_success(
            DocType.is_doc, doc_url
        ) is None
        if is_new:
            doc_txt = _("New document")
        else:
            doc_date = self.core.call_success(DocStorage.doc_get_date_by_id, doc_id)
            if doc_date is not None:
                doc_txt = self.core.call_success(I18n.i18n_date_short, doc_date)
            else:
                doc_txt = doc_id
        label = Gtk.Label.new(doc_txt)
        label.set_visible(True)
        custom_flowlayout.add_child(label, Gtk.Align.START)

    @openpaperwork_core.noop
    def on_doclist_initialized(self):
        pass

    @openpaperwork_core.noop
    def on_doc_list_clear(self):
        pass

    @openpaperwork_core.noop
    def on_doc_list_visibility_changed(self):
        pass

    @openpaperwork_core.noop
    def on_doc_box_visible(self, doc_id, row, layout):
        pass
