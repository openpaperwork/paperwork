"""
Spatial indexer that works in a way very similar to R-tree. Except for the
way the nodes are split because I'm a lazy bastard and it's good enough.
"""
import math
import logging

from openpaperwork_core.interfaces.spatial_index import AbstractSpatialIndexer
from openpaperwork_core.interfaces.spatial_index import SpatialIndex
import openpaperwork_core


LOGGER = logging.getLogger(__name__)
NB_CHILDREN_PER_NODES = 4  # must be a multiple of 2 because I'm a lazy bastard

# Node: R-tree page (leaf or not)
# Non-leaf: children are other nodes
# Leaf: last R-tree node: children are tuples (box, obj)


def compute_area(box):
    return abs((box[1][0] - box[0][0]) * (box[1][1] - box[0][1]))


class Node:
    def __init__(self, box=None):
        self.leaf = True
        self.children = []

        self.box = None
        self.area = 0
        self.set_box(box)

        self.parent = None

    def compute_enlargment(self, box):
        enlarged = (
            (
                min(self.box[0][0], box[0][0]),
                min(self.box[0][1], box[0][1]),
            ),
            (
                max(self.box[1][0], box[1][0]),
                max(self.box[1][1], box[1][1]),
            ),
        )
        enlarged = compute_area(enlarged)
        return enlarged - self.area

    def set_box(self, box):
        self.box = box
        if box is None:  # root node
            self.area = math.inf
        else:
            self.area = compute_area(box)

    def recompute_box(self, recurse=True):
        depth = 0
        s = self
        while True:
            depth += 1
            assert depth < 512
            if s.leaf:
                box = (
                    (
                        min(x[0][0][0] for x in s.children),
                        min(x[0][0][1] for x in s.children),
                    ),
                    (
                        max(x[0][1][0] for x in s.children),
                        max(x[0][1][1] for x in s.children),
                    ),
                )
            else:
                box = (
                    (
                        min(x.box[0][0] for x in s.children),
                        min(x.box[0][1] for x in s.children),
                    ),
                    (
                        max(x.box[1][0] for x in s.children),
                        max(x.box[1][1] for x in s.children),
                    ),
                )
            s.set_box(box)
            if not recurse or s.parent is None:
                break
            s = s.parent

    def is_full(self):
        assert self.leaf
        return len(self.children) >= NB_CHILDREN_PER_NODES

    @staticmethod
    def _pick_seed(boxes):
        """
        Returns a pair of nodes that would be the most wasteful.
        (see Guttman Quadratic Split algorithm)
        """

        assert len(boxes) >= 2

        if len(boxes) == 2:  # minor optim
            return tuple(boxes)

        max_waste = -1
        r = None

        for (a_idx, a) in enumerate(boxes):
            for b in boxes[a_idx + 1:]:
                new_rect = (
                    (
                        min(a[0][0][0], b[0][0][0]),
                        min(a[0][0][1], b[0][0][1]),
                    ),
                    (
                        max(a[0][1][0], b[0][1][0]),
                        max(a[0][1][1], b[0][1][1]),
                    )
                )
                new_area = (
                    (new_rect[1][0] - new_rect[0][0]) *
                    (new_rect[1][1] - new_rect[0][1])
                )
                waste = new_area - a[2] - b[2]
                if waste > max_waste or r is None:
                    r = (a, b)

        assert r is not None
        return r

    def split(self):
        assert self.leaf

        our_children = self.children
        picked = []

        while len(our_children) > 0:
            p = self._pick_seed(our_children)
            picked.append(p)
            for c in p:
                our_children.remove(c)

        node_a = Node()
        node_a.parent = self
        node_a.children = [b[0] for b in picked]
        node_a.recompute_box(recurse=False)

        node_b = Node()
        node_b.parent = self
        node_b.children = [b[1] for b in picked]
        node_b.recompute_box(recurse=False)

        self.children = [node_a, node_b]

        self.leaf = False

    def insert_box(self, box):
        assert self.leaf
        self.children.append(box)
        self.recompute_box()

    def __gt__(self, o):
        return False


class RTreeSpatialIndexer(AbstractSpatialIndexer):
    def __init__(self, boxes):
        self.root = Node()

        boxes = list(boxes)
        LOGGER.info("Loading %d boxes in rtree", len(boxes))

        for (pos, obj) in boxes:
            self.insert(pos, obj)

        # self.print_stats()

    def print_stats(self):
        """
        Not used at the moment, but useful to make sure the tree looks OK when
        debugging.
        """
        nb_boxes = 0
        nb_nodes = 0
        max_depth = 0

        to_examine = [(0, self.root)]
        while len(to_examine) > 0:
            nb_nodes += 1

            (depth, n) = to_examine.pop(0)
            max_depth = max(max_depth, depth)

            if n.leaf:
                nb_boxes += len(n.children)
            else:
                for c in n.children:
                    to_examine.append((depth + 1, c))

        LOGGER.info(
            "Rtree: %d boxes, %d nodes, max depth: %d",
            nb_boxes, nb_nodes, max_depth
        )

    def _choose_leaf(self, box_position, node):
        # keep picking up the child node that overlap as much of
        # box_position as possible
        return min({
            (c.compute_enlargment(box_position), c)
            for c in node.children
        })[1]

    def _find_leaf(self, box_position, root=None):
        if root is None:
            n = self.root
        else:
            n = root
        while not n.leaf:
            n = self._choose_leaf(box_position, n)
        return n

    def insert(self, box_position, obj):
        new_child = (box_position, obj, compute_area(box_position))
        leaf = self._find_leaf(box_position)
        if leaf.is_full():
            leaf.split()
            leaf = self._find_leaf(box_position, leaf)
        leaf.insert_box(new_child)

    @staticmethod
    def is_in(box_position, pt_x, pt_y):
        if box_position[0][0] > pt_x:
            return False
        if box_position[0][1] > pt_y:
            return False
        if box_position[1][0] < pt_x:
            return False
        if box_position[1][1] < pt_y:
            return False
        return True

    def get_boxes(self, pt_x, pt_y):
        """
        Returns all the boxes that contains the point (pt_x, pt_y)
        """
        examined = 0
        to_examine = [self.root]
        while len(to_examine) > 0:
            n = to_examine.pop(0)
            examined += 1
            if not n.leaf:
                for c in n.children:
                    if self.is_in(c.box, pt_x, pt_y):
                        to_examine.append(c)
            else:
                for c in n.children:
                    if self.is_in(c[0], pt_x, pt_y):
                        yield (c[0], c[1])
        # LOGGER.debug("Examined nodes: %d", examined)


class Plugin(
    openpaperwork_core.PluginBase,
    SpatialIndex,
):
    def spatial_indexer_get(self, boxes):
        return RTreeSpatialIndexer(boxes)
