import logging

import openpaperwork_core

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_actions import DocActions
from paperwork_gtk.interfaces.doc_list import DocListListener


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_delete"


class Plugin(
    openpaperwork_core.PluginBase,
    DocListListener,
):
    PRIORITY = -100

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocActions,
                defaults=['paperwork_gtk.mainwindow.doclist'],
            ),
        ]

    def on_doclist_initialized(self):
        self.core.call_all(
            DocActions.add_doc_action, _("Delete document"), "win." + ACTION_NAME
        )

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
