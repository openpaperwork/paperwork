import logging

import openpaperwork_core
import openpaperwork_core.util
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.gui import GuiListener

from paperwork_backend.interfaces.doc_labels import DocLabels
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    GuiListener,
    metaclass=openpaperwork_core.util.Singleton
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': DocLabels,
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.sync_started = False
        setting = self.core.call_success(
            Config.config_build_simple, "GUI", "sync_on_start",
            default_value_func=lambda: True
        )
        self.core.call_all(Config.config_register, "sync_on_start", setting)

    def on_gui_initialized(self):
        if self.sync_started:
            # in case we have many main windows opened / many cores started
            return
        self.sync_started = True
        r = self.core.call_success(Config.config_get, "sync_on_start")
        if r:
            LOGGER.info("Starting synchronization ...")
            self.core.call_all(DocTransactionManager.transaction_sync_all)
        else:
            LOGGER.info(
                "Synchronization on start is disabled --> Just loading labels"
            )
            promises = []
            self.core.call_all(DocLabels.label_load_all, promises)
            promise = promises[0]
            for p in promises[1:]:
                promise = promise.then(p)
            # use transaction_schedule to make sure that document imports
            # are not done at the same time.
            self.core.call_one(DocTransactionManager.transaction_schedule, promise)

    @openpaperwork_core.noop
    def new_mainwindow(self):
        pass
