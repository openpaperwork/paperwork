from typing import Tuple
import abc


class AbstractSpatialIndexer(abc.ABC):
    @abc.abstractmethod
    def insert(self, box_position: Tuple[Tuple[int, int], Tuple[int, int]], obj):
        ...

    @abc.abstractmethod
    def get_boxes(self, pt_x, pt_y):
        ...


class SpatialIndex(abc.ABC):
    @abc.abstractmethod
    def spatial_indexer_get(self, boxes) -> AbstractSpatialIndexer:
        ...
