import openpaperwork_core


class SpatialIndexer(object):
    def __init__(self, boxes):
        self.boxes = list(boxes)

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


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'spatial_index',
        ]

    def spatial_indexer_get(self, boxes):
        return SpatialIndexer(boxes)
