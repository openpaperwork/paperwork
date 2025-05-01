import logging

import openpaperwork_core
from paperwork_backend.interfaces.docs import DocOpener

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_actions import DocActions
from paperwork_gtk.interfaces.doc_properties import DocProperties


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_properties"


class Plugin(
    openpaperwork_core.PluginBase,
    DocOpener,
):
    PRIORITY = 100

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocActions,
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': DocProperties,
                'defaults': ['paperwork_gtk.mainwindow.docproperties'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.active_doc = None
        self.core.call_all(
            DocActions.add_doc_main_action,
            "document-properties-symbolic",
            _("Document properties"),
            self._open_properties
        )

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    @openpaperwork_core.noop
    def doc_reload(self):
        pass

    def doc_close(self):
        self.active_doc = None

    def _open_properties(self, *args, **kwargs):
        assert self.active_doc is not None
        active = self.active_doc

        LOGGER.info("Opening properties of document %s", active[0])
        self.core.call_all(DocProperties.open_doc_properties, *active)
