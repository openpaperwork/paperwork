import gc
import logging
import tempfile
import weakref

import objgraph

from openpaperwork_core import PluginBase
from openpaperwork_core.interfaces.memleak_detector import MemleakDetector


LOGGER = logging.getLogger(__name__)


class Plugin(
    PluginBase,
    MemleakDetector,
):
    def __init__(self, core):
        super().__init__(core)
        self.objs = []
        self.graph_path = tempfile.mktemp(suffix='.png')

    def on_objref_track(self, obj):
        assert obj is not None
        self.objs.append((str(type(obj)), weakref.ref(obj)))

    def on_objref_graph(self):
        to_graph = []

        objs = self.objs.copy()
        gc.collect()
        for (idx, (type_name, wref)) in reversed(list(enumerate(objs))):
            obj = wref()
            if obj is None:
                LOGGER.info("Object of type %s has disappeared", type_name)
                self.objs.pop(idx)
                continue
            to_graph.append(obj)

        if len(to_graph) <= 0:
            LOGGER.info("Nothing to graph")
            return

        LOGGER.info(
            "Making reference graph for %d objects to %s",
            len(to_graph), self.graph_path
        )
        objgraph.show_backrefs(to_graph, filename=self.graph_path)

    def on_memleak_track_stop(self):
        LOGGER.info("Most common object types:")
        objgraph.show_most_common_types()
