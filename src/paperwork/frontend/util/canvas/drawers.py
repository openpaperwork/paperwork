#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

import math
import logging

from paperwork.backend.util import image2surface


logger = logging.getLogger(__name__)


class Drawer(object):
    # layer number == priority --> higher is drawn first (lower level)
    BACKGROUND_LAYER = 1000
    IMG_LAYER = 200
    BOX_LAYER = 50
    PROGRESSION_INDICATOR_LAYER = 25
    FADDING_EFFECT_LAYER = 0
    # layer number == priority --> lower is drawn last (higher level)

    layer = -1  # must be set by subclass

    position = (0, 0)  # (x, y)
    size = (0, 0)  # (width, height)
    angle = 0

    def __init__(self):
        self.canvas = None

    def set_canvas(self, canvas):
        self.canvas = canvas

    @staticmethod
    def compute_visibility(offset, visible_area_size, position, size):
        should_be_visible = True
        if (position[0] + size[0] < offset[0]):
            should_be_visible = False
        elif (offset[0] + visible_area_size[0] < position[0]):
            should_be_visible = False
        elif (position[1] + size[1] < offset[1]):
            should_be_visible = False
        elif (offset[1] + visible_area_size[1] < position[1]):
            should_be_visible = False
        return should_be_visible

    def draw_surface(self, cairo_ctx, surface, img_position, img_size, angle=0):
        """
        Draw a surface

        Arguments:
            cairo_ctx --- cairo context to draw on
            surface --- surface to draw on the context
            img_position --- target position for the surface once on the canvas
            img_size --- target size for the surface once on the canvas
            angle --- rotation to apply (WARNING: applied after positioning,
                      and rotated at the center of the surface !)
        """
        angle = math.pi * angle / 180
        surface_size = (surface.get_width(), surface.get_height())
        scaling = (
            (float(img_size[0]) / float(surface_size[0])),
            (float(img_size[1]) / float(surface_size[1])),
        )

        # some drawer call draw_surface() many times, so we save the
        # context here
        cairo_ctx.save()
        try:
            cairo_ctx.translate(img_position[0], img_position[1])
            cairo_ctx.translate(-self.canvas.offset[0], -self.canvas.offset[1])
            if angle != 0:
                cairo_ctx.translate(img_size[0] / 2, img_size[1] / 2)
                cairo_ctx.rotate(angle)
                cairo_ctx.translate(-img_size[0] / 2, -img_size[1] / 2)
            cairo_ctx.scale(scaling[0], scaling[1])

            cairo_ctx.set_source_surface(
                surface, 0, 0)
            cairo_ctx.rectangle(0, 0,
                                surface_size[0],
                                surface_size[1])
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()

    def do_draw(self, cairo_ctx):
        """
        Arguments:
            offset --- Position of the area in which to draw:
                       (offset_x, offset_y)
            size --- Size of the area in which to draw: (width, height) = size
        """
        assert()

    def on_tick(self):
        """
        Called every 1/27 second
        """
        pass

    def draw(self, cairo_ctx):
        # don't bother drawing if it's not visible
        if self.canvas.offset[0] + self.canvas.size[0] < self.position[0]:
            return
        if self.canvas.offset[1] + self.canvas.size[1] < self.position[1]:
            return
        if self.position[0] + self.size[0] < self.canvas.offset[0]:
            return
        if self.position[1] + self.size[1] < self.canvas.offset[1]:
            return
        self.do_draw(cairo_ctx)

    def _get_relative_position(self):
        position = self.position
        if self.angle:
            # enlarge the area
            size = self.size
            min_size = min(size)
            max_size = max(size)
            diff = max_size - min_size
            if size[0] < size[1]:
                position = (position[0] - (diff / 2), position[1])
            else:
                position = (position[0], position[1] - (diff / 2))

        p = (max(0, position[0] - self.canvas.offset[0]),
             max(0, position[1] - self.canvas.offset[1]))
        p = (min(p[0], self.canvas.size[0]),
             min(p[1], self.canvas.size[1]))
        return p

    relative_position = property(_get_relative_position)

    def _get_relative_edge(self):
        position = self.position
        size = self.size
        if self.angle:
            # enlarge the area
            min_size = min(size)
            max_size = max(size)
            diff = max_size - min_size
            if size[0] < size[1]:
                position = (position[0] - (diff / 2), position[1])
            else:
                position = (position[0], position[1] - (diff / 2))
            size = (max_size, max_size)

        edge = (position[0] + size[0],
                position[1] + size[1])
        edge = (max(0, edge[0] - self.canvas.offset[0]),
                max(0, edge[1] - self.canvas.offset[1]))
        edge = (min(edge[0], self.canvas.size[0]),
                min(edge[1], self.canvas.size[1]))
        return edge

    def _get_relative_size(self):
        edge = self._get_relative_edge()
        rel_p = self.relative_position
        size = (edge[0] - rel_p[0], edge[1] - rel_p[1])
        return size

    relative_size = property(_get_relative_size)

    def redraw(self):
        self.canvas.redraw((self.relative_position,
                            self.relative_size))

    def show(self):
        pass

    def hide(self):
        pass


class BackgroundDrawer(Drawer):
    layer = Drawer.BACKGROUND_LAYER

    def __init__(self, rgb):
        Drawer.__init__(self)
        self.rgb = rgb
        self.position = (0, 0)

    def __get_size(self):
        assert(self.canvas is not None)
        return (self.canvas.full_size[0], self.canvas.full_size[1])

    size = property(__get_size)

    def do_draw(self, cairo_ctx):
        cairo_ctx.set_source_rgb(self.rgb[0], self.rgb[1], self.rgb[2])
        cairo_ctx.rectangle(0, 0, self.canvas.size[0], self.canvas.size[1])
        cairo_ctx.clip()
        cairo_ctx.paint()


class RectangleDrawer(Drawer):
    layer = Drawer.BOX_LAYER
    visible = True

    def __init__(self,
                 position, size,
                 inside_color=(0.0, 0.0, 1.0, 1.0),
                 angle=0):
        Drawer.__init__(self)
        self.position = position
        self.size = size
        self.inside_color = inside_color
        self.angle = angle

    def do_draw(self, cairo_ctx):
        cairo_ctx.save()
        try:
            if (len(self.inside_color) > 3):
                cairo_ctx.set_source_rgba(
                    self.inside_color[0], self.inside_color[1],
                    self.inside_color[2], self.inside_color[3]
                )
            else:
                cairo_ctx.set_source_rgb(
                    self.inside_color[0], self.inside_color[1],
                    self.inside_color[2]
                )
            cairo_ctx.set_line_width(2.0)

            if self.angle != 0:
                angle = math.pi * self.angle / 180
                cairo_ctx.translate(self.position[0] - self.canvas.offset[0]
                                    + (self.size[0] / 2),
                                    self.position[1] - self.canvas.offset[1]
                                    + (self.size[1] / 2))
                cairo_ctx.rotate(angle)
                cairo_ctx.translate(-self.position[0] + self.canvas.offset[0]
                                    - (self.size[0] / 2),
                                    -self.position[1] + self.canvas.offset[1]
                                    - (self.size[1] / 2))

            cairo_ctx.rectangle(
                self.position[0] - self.canvas.offset[0],
                self.position[1] - self.canvas.offset[1],
                self.size[0], self.size[1]
            )
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()


class LineDrawer(Drawer):
    layer = Drawer.BOX_LAYER
    visible = True

    def __init__(self,
                 start_point, end_point,
                 width=1.0,
                 color=(0.0, 0.0, 0.0, 1.0)):
        Drawer.__init__(self)

        self.start = start_point
        self.end = end_point
        self.width = width
        self.color = color

    def _get_position(self):
        return (
            min(self.start[0], self.end[0]),
            min(self.start[1], self.end[1]),
        )

    def _set_position(self, new):
        old = self.position
        offset = (
            new[0] - old[0],
            new[1] - old[1],
        )
        self.start = (
            self.start[0] + offset[0],
            self.start[1] + offset[1],
        )
        self.end = (
            self.end[0] + offset[0],
            self.end[1] + offset[1],
        )

    position = property(_get_position, _set_position)

    def _get_size(self):
        return (
            max(self.start[0], self.end[0]) - min(self.start[0], self.end[0]),
            max(self.start[1], self.end[1]) - min(self.start[1], self.end[1]),
        )

    size = property(_get_size)

    def do_draw(self, cairo_ctx):
        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(self.color[0], self.color[1],
                                      self.color[2], self.color[3])
            cairo_ctx.set_line_width(self.width)
            cairo_ctx.move_to(self.start[0] - self.canvas.offset[0],
                              self.start[1] - self.canvas.offset[1])
            cairo_ctx.line_to(self.end[0] - self.canvas.offset[0],
                              self.end[1] - self.canvas.offset[1])
            cairo_ctx.stroke()
        finally:
            cairo_ctx.restore()


class PillowImageDrawer(Drawer):
    layer = Drawer.IMG_LAYER
    visible = True

    def __init__(self, position, image):
        Drawer.__init__(self)
        self.size = image.size
        self.img_size = self.size
        self.position = position
        self.angle = 0
        self.surface = image2surface(image)

    def do_draw(self, cairo_ctx):
        self.draw_surface(cairo_ctx,
                          self.surface, self.position,
                          self.size, self.angle)


class TargetAreaDrawer(Drawer):
    layer = Drawer.BOX_LAYER
    visible = True

    def __init__(self,
                 position, size,
                 target_position, target_size,
                 rect_color=(0.0, 0.0, 1.0, 1.0),
                 out_color=(0.0, 0.0, 1.0, 0.1)):
        Drawer.__init__(self)

        assert(position[0] <= target_position[0])
        assert(position[1] <= target_position[1])
        assert(position[0] + size[0] >= target_position[0] + target_size[0])
        assert(position[1] + size[1] >= target_position[1] + target_size[1])

        self._position = position
        self.size = size
        self.target_position = target_position
        self.target_size = target_size
        self.rect_color = rect_color
        self.out_color = out_color

        logger.info("Drawer: Target area: %s (%s) << %s (%s)"
                    % (str(self._position), str(self.size),
                       str(self.target_position), str(self.target_size)))

    def _get_position(self):
        return self._position

    def _set_position(self, new_position):
        offset = (
            new_position[0] - self._position[0],
            new_position[1] - self._position[1],
        )
        self._position = new_position
        self.target_position = (
            self.target_position[0] + offset[0],
            self.target_position[1] + offset[1],
        )

    position = property(_get_position, _set_position)

    def _draw_rect(self, cairo_ctx, rect):
        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(self.rect_color[0], self.rect_color[1],
                                      self.rect_color[2], self.rect_color[3])
            cairo_ctx.set_line_width(2.0)
            cairo_ctx.rectangle(rect[0][0], rect[0][1],
                                rect[1][0] - rect[0][0],
                                rect[1][1] - rect[0][1])
            cairo_ctx.stroke()
        finally:
            cairo_ctx.restore()

    def _draw_area(self, cairo_ctx, rect):
        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(self.out_color[0], self.out_color[1],
                                      self.out_color[2], self.out_color[3])
            cairo_ctx.rectangle(rect[0][0], rect[0][1],
                                rect[1][0] - rect[0][0],
                                rect[1][1] - rect[0][1])
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()

    def do_draw(self, cairo_ctx):
        # we draw *outside* of the target but inside of the whole
        # area
        rects = [
            (
                # left
                self._draw_area,
                (
                    (self._position[0], self._position[1]),
                    (self.target_position[0],
                     self._position[1] + self.size[1]),
                )
            ),
            (
                # top
                self._draw_area,
                (
                    (self.target_position[0], self._position[1]),
                    (
                        self.target_position[0] + self.target_size[0],
                        self.target_position[1]
                    ),
                )
            ),
            (
                # right
                self._draw_area,
                (
                    (
                        self.target_position[0] + self.target_size[0],
                        self._position[1]),
                    (
                        self._position[0] + self.size[0],
                        self._position[1] + self.size[1]
                    ),
                )
            ),
            (
                # bottom
                self._draw_area,
                (
                    (self.target_position[0],
                     self.target_position[1] + self.target_size[1]),
                    (
                        self.target_position[0] + self.target_size[0],
                        self._position[1] + self.size[1]
                    )
                )
            ),
            (
                # target area
                self._draw_rect,
                (
                    (self.target_position[0], self.target_position[1]),
                    (
                        self.target_position[0] + self.target_size[0],
                        self.target_position[1] + self.target_size[1]
                    ),
                )
            ),
        ]

        rects = [
            (
                func,
                (
                    (
                        rect[0][0] - self.canvas.offset[0],
                        rect[0][1] - self.canvas.offset[1],
                    ),
                    (
                        rect[1][0] - self.canvas.offset[0],
                        rect[1][1] - self.canvas.offset[1],
                    ),
                )
            )
            for (func, rect) in rects
        ]

        for (func, rect) in rects:
            func(cairo_ctx, rect)


def fit(element_size, area_size, force=False):
    """
    Return the size to give to the element so it fits in the area size.
    Keep aspect ratio.
    """
    if not force:
        ratio = min(
            1.0,
            float(area_size[0]) / float(element_size[0]),
            float(area_size[1]) / float(element_size[1]),
        )
    else:
        ratio = min(
            float(area_size[0]) / float(element_size[0]),
            float(area_size[1]) / float(element_size[1]),
        )

    return (
        int(element_size[0] * ratio),
        int(element_size[1] * ratio),
    )
