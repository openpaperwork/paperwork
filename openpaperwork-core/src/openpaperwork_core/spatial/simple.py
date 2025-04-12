from openpaperwork_core.interfaces.spatial_index import AbstractSpatialIndexer
from openpaperwork_core.interfaces.spatial_index import SpatialIndex
import openpaperwork_core


class SpatialIndexer(AbstractSpatialIndexer):
    def __init__(self, boxes):
        self.boxes = list(boxes)

    def insert(self, box_position, obj):
        self.boxes.append((box_position, obj))

    def get_boxes(self, pt_x, pt_y):
        for (pos, obj) in self.boxes:
            if pos[0][0] > pt_x:
                continue
            if pos[0][1] > pt_y:
                continue
            if pos[1][0] < pt_x:
                continue
            if pos[1][1] < pt_y:
                continue
            yield (pos, obj)


class Plugin(
    openpaperwork_core.PluginBase,
    SpatialIndex,
):
    def spatial_indexer_get(self, boxes):
        return SpatialIndexer(boxes)
