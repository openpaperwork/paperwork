from gi.repository import Gdk
from gi.repository import Gtk

from paperwork.backend.util import image2surface


class Drawer(object):
    # layer number == priority --> higher is drawn first
    BACKGROUND_LAYER = 1000
    IMG_LAYER = 200
    PROGRESSION_INDICATOR_LAYER = 100
    BOX_LAYER = 50
    SPINNER_LAYER = 25
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
    def draw_surface(cairo_context, canvas_offset, canvas_size,
                     surface, img_position, img_size):
        surface_size = (surface.get_width(), surface.get_height())
        scaling = (
            (float(img_size[0]) / float(surface_size[0])),
            (float(img_size[1]) / float(surface_size[1])),
        )

        # scaling is applied *after* all the other transformations
        # of user space.
        canvas_offset = (
            canvas_offset[0] / scaling[0],
            canvas_offset[1] / scaling[1],
        )
        img_position = (
            img_position[0] / scaling[0],
            img_position[1] / scaling[1],
        )
        img_size = (
            img_size[0] / scaling[0],
            img_size[1] / scaling[1]
        )

        img_offset = (max(0, canvas_offset[0] - img_position[0]),
                      max(0, canvas_offset[1] - img_position[1]))
        target_offset = (max(0, img_position[0] - canvas_offset[0]),
                         max(0, img_position[1] - canvas_offset[1]))

        # some drawer call draw_surface() many times, so we save the
        # context here
        cairo_context.save()
        try:
            cairo_context.scale(scaling[0], scaling[1])
            cairo_context.set_source_surface(
                surface,
                (target_offset[0] - img_offset[0]),
                (target_offset[1] - img_offset[1]),
            )
            cairo_context.rectangle(target_offset[0],
                                    target_offset[1],
                                    img_size[0],
                                    img_size[1])
            cairo_context.clip()
            cairo_context.paint()
        finally:
            cairo_context.restore()


    def do_draw(self, cairo_context, offset, size):
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

    def draw(self, cairo_context, offset, visible_size):
        # don't bother drawing if it's not visible
        if offset[0] + visible_size[0] < self.position[0]:
            return
        if offset[1] + visible_size[1] < self.position[1]:
            return
        if self.position[0] + self.size[0] < offset[0]:
            return
        if self.position[1] + self.size[1] < offset[1]:
            return
        self.do_draw(cairo_context, offset, visible_size)

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

    def do_draw(self, cairo_context, offset, size):
        cairo_context.set_source_rgb(self.rgb[0], self.rgb[1], self.rgb[2])
        cairo_context.rectangle(0, 0, size[0], size[1])
        cairo_context.clip()
        cairo_context.paint()


class PillowImageDrawer(Drawer):
    layer = Drawer.IMG_LAYER
    visible = True

    def __init__(self, position, image):
        self.size = image.size
        self.position = position
        self.surface = image2surface(image)

    def do_draw(self, cairo_context, offset, size):
        self.draw_surface(cairo_context, offset, size,
                          self.surface, self.position, self.size)


class ScanDrawer(Drawer):
    layer = Drawer.IMG_LAYER

    visible = True

    def __init__(self, position, scan_size, visible_size):
        Drawer.__init__(self)
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

    def add_chunk(self, line, img_chunk):
        surface = image2surface(img_chunk)
        self.surfaces.append((line, surface))
        self.canvas.redraw()

    def do_draw(self, cairo_context, canvas_offset, canvas_size):
        for (line, surface) in self.surfaces:
            line *= self.ratio
            chunk_size = (surface.get_width() * self.ratio,
                          surface.get_height() * self.ratio)
            self.draw_surface(cairo_context, canvas_offset, canvas_size,
                              surface, (float(self.position[0]),
                                        float(self.position[1]) + line),
                              chunk_size)


class SpinnerDrawer(Drawer):
    ICON_SIZE = 48

    layer = Drawer.SPINNER_LAYER

    def __init__(self, position):
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
