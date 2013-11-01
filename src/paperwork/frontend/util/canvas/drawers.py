import cairo
import math

from gi.repository import Gdk
from gi.repository import Gtk

from paperwork.backend.util import image2surface
from paperwork.frontend.util.canvas import Canvas


class Drawer(object):
    # layer number == priority --> higher is drawn first
    BACKGROUND_LAYER = 1000
    IMG_LAYER = 200
    BOX_LAYER = 50
    PROGRESSION_INDICATOR_LAYER = 25
    FADDING_EFFECT_LAYER = 0
    # layer number == priority --> lower is drawn last

    layer = -1  # must be set by subclass

    position = (0, 0)  # (x, y)
    size = (0, 0)  # (width, height)

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

    @staticmethod
    def draw_surface(cairo_ctx, canvas_offset, canvas_size,
                     surface, img_position, img_size, angle=0):
        surface_size = (surface.get_width(), surface.get_height())
        scaling = (
            (float(img_size[0]) / float(surface_size[0])),
            (float(img_size[1]) / float(surface_size[1])),
        )

        scaled_img_size = (
            img_size[0] / scaling[0],
            img_size[1] / scaling[1]
        )

        # some drawer call draw_surface() many times, so we save the
        # context here
        cairo_ctx.save()
        try:
            cairo_ctx.translate(img_position[0], img_position[1])
            if angle != 0:
                cairo_ctx.translate(img_size[0] / 2, img_size[1] / 2)
                cairo_ctx.rotate(math.pi * angle / 180)
                cairo_ctx.translate(-img_size[0] / 2, -img_size[1] / 2)
            cairo_ctx.translate(-canvas_offset[0], -canvas_offset[1])
            cairo_ctx.scale(scaling[0], scaling[1])

            cairo_ctx.set_source_surface(
                surface, 0, 0)
            cairo_ctx.rectangle(0, 0,
                                scaled_img_size[0],
                                scaled_img_size[1])
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()


    def do_draw(self, cairo_ctx, offset, size):
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

    def draw(self, cairo_ctx, offset, visible_size):
        # don't bother drawing if it's not visible
        if offset[0] + visible_size[0] < self.position[0]:
            return
        if offset[1] + visible_size[1] < self.position[1]:
            return
        if self.position[0] + self.size[0] < offset[0]:
            return
        if self.position[1] + self.size[1] < offset[1]:
            return
        self.do_draw(cairo_ctx, offset, visible_size)

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

    def do_draw(self, cairo_ctx, offset, size):
        cairo_ctx.set_source_rgb(self.rgb[0], self.rgb[1], self.rgb[2])
        cairo_ctx.rectangle(0, 0, size[0], size[1])
        cairo_ctx.clip()
        cairo_ctx.paint()


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

    def fit(self, size_to_fit_in):
        ratio = min(
            1.0,
            float(size_to_fit_in[0]) / float(self.img_size[0]),
            float(size_to_fit_in[1]) / float(self.img_size[1]),
        )
        self.size = (
            int(ratio * self.img_size[0]),
            int(ratio * self.img_size[1]),
        )

    def do_draw(self, cairo_ctx, offset, size):
        self.draw_surface(cairo_ctx, offset, size,
                          self.surface, self.position, self.size, self.angle)
