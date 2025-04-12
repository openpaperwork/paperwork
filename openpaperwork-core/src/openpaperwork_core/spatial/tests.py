import unittest

from openpaperwork_core.interfaces.spatial_index import SpatialIndex
import openpaperwork_core


class AbstractTest(unittest.TestCase):
    def get_plugin_name(self):
        """
        Must be overloaded by subclasses
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_basic(self):
        boxes = [
            (((0, 0), (10, 10)), "a"),
            (((10, 10), (50, 40)), "b"),
            (((25, 25), (100, 100)), "c"),
        ]
        indexer = self.core.call_success(SpatialIndex.spatial_indexer_get, boxes)
        self.assertEqual(
            list(indexer.get_boxes(5, 5)),
            [
                (((0, 0), (10, 10)), "a"),
            ]
        )
        self.assertEqual(
            list(indexer.get_boxes(5, 10)),
            [
                (((0, 0), (10, 10)), "a"),
            ]
        )
        self.assertEqual(
            list(indexer.get_boxes(10, 10)),
            [
                (((0, 0), (10, 10)), "a"),
                (((10, 10), (50, 40)), "b"),
            ]
        )
        self.assertEqual(
            list(indexer.get_boxes(25, 20)),
            [
                (((10, 10), (50, 40)), "b"),
            ]
        )
        self.assertEqual(
            list(indexer.get_boxes(75, 75)),
            [
                (((25, 25), (100, 100)), "c"),
            ]
        )

    def test_real(self):
        boxes = [
            (((584, 360), (1097, 415)), "CROIX-ROUGE"),
            (((1126, 361), (1540, 428)), "FRANCAISE"),
            (((865, 430), (1006, 464)), "EQUIPES"),
            (((1028, 437), (1258, 462)), "SECOURISTES"),
            (((724, 675), (911, 718)), "Madame"),
        ]
        indexer = self.core.call_success(SpatialIndex.spatial_indexer_get, boxes)
        self.assertEqual(
            list(indexer.get_boxes(836, 701)),
            [
                (((724, 675), (911, 718)), "Madame"),
            ]
        )
