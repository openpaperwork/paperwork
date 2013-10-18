import math

import cairo

from gi.repository import Gdk
from gi.repository import Gtk

from paperwork.backend.util import image2surface
from paperwork.frontend.util.canvas import Canvas
from paperwork.frontend.util.canvas.drawers import Drawer


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

        self.anim = {
            "position": 0,
            "offset": (float(self.size[1])
                       / (self.ANIM_LENGTH
                          / Canvas.TICK_INTERVAL)),
        }

    def on_tick(self):
        self.anim['position'] += self.anim['offset']
        if self.anim['position'] < 0 or self.anim['position'] >= self.size[0]:
            self.anim['position'] = max(0, self.anim['position'])
            self.anim['position'] = min(self.size[0], self.anim['position'])
            self.anim['offset'] *= -1

    def add_chunk(self, line, img_chunk):
        surface = image2surface(img_chunk)
        self.surfaces.append((line, surface))
        self.canvas.redraw()

    def draw_chunks(self, cairo_ctx, canvas_offset, canvas_size):
        for (line, surface) in self.surfaces:
            line *= self.ratio
            chunk_size = (surface.get_width() * self.ratio,
                          surface.get_height() * self.ratio)
            self.draw_surface(cairo_ctx, canvas_offset, canvas_size,
                              surface, (float(self.position[0]),
                                        float(self.position[1]) + line),
                              chunk_size)

    def draw_animation(self, cairo_ctx, canvas_offset, canvas_size):
        if len(self.surfaces) <= 0:
            return

        position = (
            self.position[0] - canvas_offset[0],
            (
                self.position[1]
                - canvas_offset[1]
                + (self.ratio * self.surfaces[-1][0])
                + (self.ratio * self.surfaces[-1][1].get_height())
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
    ICON_SIZE = 48

    layer = Drawer.PROGRESSION_INDICATOR_LAYER

    def __init__(self, position):
        Animation.__init__(self)
        self.visible = False
        self.position = position
        self.size = (self.ICON_SIZE, self.ICON_SIZE)

        icon_theme = Gtk.IconTheme.get_default()
        icon_info = icon_theme.lookup_icon("process-working", self.ICON_SIZE,
                                           Gtk.IconLookupFlags.NO_SVG)
        self.icon_pixbuf = icon_info.load_icon()
        self.frame = 1
        self.nb_frames = (
            (self.icon_pixbuf.get_width() / self.ICON_SIZE),
            (self.icon_pixbuf.get_height() / self.ICON_SIZE),
        )

    def on_tick(self):
        self.frame += 1
        self.frame %= (self.nb_frames[0] * self.nb_frames[1])
        if self.frame == 0:
            # XXX(Jflesch): skip the first frame:
            # in gnome-spinner.png, the first frame is empty.
            # don't know why.
            self.frame += 1

    def draw(self, cairo_ctx, canvas_offset, canvas_visible_size):
        frame = (
            (self.frame % self.nb_frames[0]),
            (self.frame / self.nb_frames[0]),
        )
        frame = (
            (frame[0] * self.ICON_SIZE),
            (frame[1] * self.ICON_SIZE),
        )

        img_offset = (max(0, canvas_offset[0] - self.position[0]),
                      max(0, canvas_offset[1] - self.position[1]))
        img_offset = (
            img_offset[0] + frame[0],
            img_offset[1] + frame[1],
        )
        target_offset = (max(0, self.position[0] - canvas_offset[0]),
                         max(0, self.position[1] - canvas_offset[1]))

        cairo_ctx.save()
        try:
            Gdk.cairo_set_source_pixbuf(cairo_ctx, self.icon_pixbuf,
                                        (target_offset[0] - img_offset[0]),
                                        (target_offset[1] - img_offset[1]),
                                       )
            cairo_ctx.rectangle(target_offset[0],
                                target_offset[1],
                                self.ICON_SIZE,
                                self.ICON_SIZE)
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()
