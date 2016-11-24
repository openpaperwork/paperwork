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

import logging
import math

import cairo
import PIL.Image

from paperwork_backend.util import image2surface
from paperwork.frontend.util import load_image
from paperwork.frontend.util.canvas import Canvas
from paperwork.frontend.util.canvas.drawers import Drawer
from paperwork.frontend.util.canvas.drawers import fit


logger = logging.getLogger(__name__)


class Animation(Drawer):
    def __init__(self):
        Drawer.__init__(self)
        self.ticks_enabled = False

    def show(self):
        Drawer.show(self)
        if not self.ticks_enabled:
            self.ticks_enabled = True
            self.canvas.start_ticks()

    def hide(self):
        Drawer.hide(self)
        if self.ticks_enabled:
            self.ticks_enabled = False
            self.canvas.stop_ticks()


class ScanAnimation(Animation):
    layer = Drawer.IMG_LAYER

    visible = True

    BACKGROUND_COLOR = (1.0, 1.0, 1.0)

    ANIM_LENGTH = 1000  # mseconds
    ANIM_HEIGHT = 5

    def __init__(self, position, scan_size, visible_size):
        Animation.__init__(self)
        self.ratio = min(
            float(visible_size[0]) / float(scan_size[0]),
            float(visible_size[1]) / float(scan_size[1]),
        )
        self.size = (
            int(self.ratio * scan_size[0]),
            int(self.ratio * scan_size[1]),
        )
        self.position = position
        self.surfaces = []
        self.last_redraw_lines = 0

        self.anim = {
            "position": 0,
            "offset": (float(self.size[1]) /
                       (self.ANIM_LENGTH /
                        Canvas.TICK_INTERVAL)),
        }

    def on_tick(self):
        self.anim['position'] += self.anim['offset']
        if self.anim['position'] < 0 or self.anim['position'] >= self.size[0]:
            self.anim['position'] = max(0, self.anim['position'])
            self.anim['position'] = min(self.size[0], self.anim['position'])
            self.anim['offset'] *= -1
        if len(self.surfaces) <= 0:
            return
        self.redraw()

    def add_chunk(self, line, img_chunk):
        # big images take more time to draw
        # --> we resize it now
        img_size = fit(img_chunk.size, self.size)
        if (img_size[0] <= 0 or img_size[1] <= 0):
            return
        img_chunk = img_chunk.resize(img_size)

        surface = image2surface(img_chunk)
        self.surfaces.append((line * self.ratio, surface))
        self.on_tick()

    def draw_chunks(self, cairo_ctx):
        position = (
            self.position[0],
            self.position[1],
        )

        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgb(self.BACKGROUND_COLOR[0],
                                     self.BACKGROUND_COLOR[1],
                                     self.BACKGROUND_COLOR[2])
            cairo_ctx.rectangle(position[0], position[1],
                                self.size[0], self.size[1])
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()

        for (line, surface) in self.surfaces:
            chunk_size = (surface.get_width(), surface.get_height())
            self.draw_surface(cairo_ctx,
                              surface, (float(self.position[0]),
                                        float(self.position[1]) + line),
                              chunk_size)

    def draw_animation(self, cairo_ctx):
        if len(self.surfaces) <= 0:
            return

        position = (
            self.position[0],
            (
                self.position[1] +
                (self.surfaces[-1][0]) +
                (self.surfaces[-1][1].get_height())
            ),
        )

        cairo_ctx.save()
        try:
            cairo_ctx.set_operator(cairo.OPERATOR_OVER)
            cairo_ctx.set_source_rgb(0.5, 0.0, 0.0)
            cairo_ctx.set_line_width(1.0)
            cairo_ctx.move_to(position[0], position[1])
            cairo_ctx.line_to(position[0] + self.size[0], position[1])
            cairo_ctx.stroke()

            cairo_ctx.set_source_rgb(1.0, 0.0, 0.0)
            cairo_ctx.arc(position[0] + self.anim['position'],
                          position[1],
                          float(self.ANIM_HEIGHT) / 2,
                          0.0, math.pi * 2)
            cairo_ctx.stroke()

        finally:
            cairo_ctx.restore()

    def do_draw(self, *args, **kwargs):
        self.draw_chunks(*args, **kwargs)
        self.draw_animation(*args, **kwargs)


class SpinnerAnimation(Animation):
    src_size = 48
    ICON_SIZE = 64

    layer = Drawer.SPINNER

    def __init__(self, position):
        Animation.__init__(self)
        self.visible = True
        self.position = position
        self.size = (self.ICON_SIZE, self.ICON_SIZE)

        img = load_image("waiting.png")
        factor = self.ICON_SIZE / self.src_size
        img = img.resize((int(img.size[0] * factor), int(img.size[1] * factor)),
                         PIL.Image.ANTIALIAS)
        img.load()
        self.icon_surface = image2surface(img)
        self.frame = 1
        self.nb_frames = (
            (max(1, img.size[0] / self.ICON_SIZE)),
            (max(1, img.size[1] / self.ICON_SIZE)),
        )

    def on_tick(self):
        if not self.icon_surface:
            return

        self.frame += 1
        self.frame %= (self.nb_frames[0] * self.nb_frames[1])
        if self.frame == 0:
            # XXX(Jflesch): skip the first frame:
            # in gnome-spinner.png, the first frame is empty.
            # don't know why.
            self.frame += 1
        self.redraw()

    def draw(self, cairo_ctx):
        if not self.icon_surface:
            return

        frame = (
            int(self.frame % self.nb_frames[0]),
            int(self.frame / self.nb_frames[0]),
        )
        frame = (
            (frame[0] * self.ICON_SIZE),
            (frame[1] * self.ICON_SIZE),
        )

        img_offset = (max(0, - self.position[0]),
                      max(0, - self.position[1]))
        img_offset = (
            img_offset[0] + frame[0],
            img_offset[1] + frame[1],
        )
        target_offset = self.position

        cairo_ctx.save()
        try:
            cairo_ctx.translate(target_offset[0], target_offset[1])
            cairo_ctx.set_source_surface(
                self.icon_surface,
                -1 * img_offset[0],
                -1 * img_offset[1],
            )
            cairo_ctx.rectangle(0, 0,
                                self.ICON_SIZE,
                                self.ICON_SIZE)
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()
