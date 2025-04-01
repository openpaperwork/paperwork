import gc
import logging

import pympler.tracker

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['memleak_detector']

    def __init__(self, core):
        super().__init__(core)
        self.tracker = None

    def on_memleak_track_start(self):
        self.tracker = None
        LOGGER.info("Garbage collecting ...")
        gc.collect()
        LOGGER.info("Starting memory leaks tracking ...")
        self.tracker = pympler.tracker.SummaryTracker()

    def on_memleak_track_stop(self):
        if self.tracker is not None:
            LOGGER.info("Garbage collecting ...")
            gc.collect()
            LOGGER.info("Stopping memory leaks tracking ...")
            self.tracker.print_diff()
        self.tracker = None
