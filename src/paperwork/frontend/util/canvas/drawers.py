from paperwork.backend.util import image2surface


class Drawer(object):
    # layer number == priority --> higher is drawn first
    BACKGROUND_LAYER = 1000
    IMG_LAYER = 200
    PROGRESSION_INDICATOR_LAYER = 100
    BOX_LAYER = 50
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
        self.rgb = rgb
        self.canvas = None
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
