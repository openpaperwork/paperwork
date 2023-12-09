import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(
            openpaperwork_core.PluginBase,
            metaclass=openpaperwork_core.util.Singleton
        ):
    def __init__(self):
        super().__init__()
        self.sync_started = False

    def get_interfaces(self):
        return ['sync_on_start']

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)
        setting = self.core.call_success(
            "config_build_simple", "GUI", "sync_on_start",
            default_value_func=lambda: True
        )
        self.core.call_all("config_register", "sync_on_start", setting)

    def on_gtk_initialized(self):
        if self.sync_started:
            # in case we have many main windows opened / many cores started
            return
        self.sync_started = True
        r = self.core.call_success("config_get", "sync_on_start")
        if r:
            LOGGER.info("Starting synchronization ...")
            self.core.call_all("transaction_sync_all")
        else:
            LOGGER.info(
                "Synchronization on start is disabled --> Just loading labels"
            )
            promises = []
            self.core.call_all("label_load_all", promises)
            promise = promises[0]
            for p in promises[1:]:
                promise = promise.then(p)
            # use transaction_schedule to make sure that document imports
            # are not done at the same time.
            self.core.call_one("transaction_schedule", promise)
