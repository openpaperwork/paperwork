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

from ... import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'gtk_doclist_listener',
            'gtk_doclist_name',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.maindow.doclist'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_doc_box_creation(self, doc_id, gtk_row, custom_flowlayout):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        is_new = doc_url is None or self.core.call_success(
            "is_doc", doc_url
        ) is None
        if is_new:
            doc_txt = _("New document")
        else:
            doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
            if doc_date is not None:
                doc_txt = self.core.call_success("i18n_date_short", doc_date)
            else:
                doc_txt = doc_id
        label = Gtk.Label.new(doc_txt)
        label.set_visible(True)
        custom_flowlayout.add_child(label, Gtk.Align.START)
