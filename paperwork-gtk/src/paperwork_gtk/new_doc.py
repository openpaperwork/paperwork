from openpaperwork_core.interfaces.config import Config

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import DocType
import openpaperwork_core

from paperwork_gtk.interfaces.new_doc import NewDoc


class Plugin(
    openpaperwork_core.PluginBase,
    NewDoc,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
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
        ]

    def __init__(self, core):
        super().__init__(core)
        self.new_doc = None
        self.core.call_all(
            Config.config_add_observer, "workdir", self._on_work_dir_changed
        )

    def _on_work_dir_changed(self):
        # Bug report 170: When the work directory has been changed,
        # we have to make sure to drop any reference to it so the user doesn't
        # use it by accident.
        # (keep in mind that self.new_doc = (doc_id, doc_url), and doc_url
        # includes the work directory path)
        self.new_doc = None
        return None

    def get_new_doc(self):
        if self.new_doc is not None:
            if self.core.call_success(DocType.is_doc, self.new_doc[1]) is None:
                return self.new_doc
        self.new_doc = self.core.call_success(DocStorage.storage_get_new_doc)
        return self.new_doc
