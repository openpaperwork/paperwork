import cairo

from paperwork.model.common.page import BasicPage
from paperwork.util import surface2image

class PdfPage(BasicPage):
    def __init__(self, doc, page_nb):
        BasicPage.__init__(self, doc, page_nb)
        self.pdf_page = doc.pdf.get_page(page_nb)
        size = self.pdf_page.get_size()
        self.size = (int(size[0]), int(size[1]))

    def __get_text(self):
        return unicode(self.pdf_page.get_text()).split(u"\n")

    text = property(__get_text)

    def __get_boxes(self):
        # TODO(Jflesch): Can't find poppler.Page.get_text_layout() ?
        return []

    boxes = property(__get_boxes)

    def __render_img(self, factor):
        # TODO(Jflesch): In a perfect world, we shouldn't use ImageSurface.
        # we should draw directly on the GtkImage.window.cairo_create() context.
        # It would be much more efficient.

        width = int(factor * self.size[0])
        height = int(factor * self.size[1])

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)
        ctx.scale(factor, factor)
        self.pdf_page.render(ctx)
        return surface2image(surface)

    def __get_img(self):
        return self.__render_img(2)

    img = property(__get_img)

    def get_thumbnail(self, width):
        factor = float(width) / self.size[0]
        return self.__render_img(factor)

    def print_page_cb(self, print_op, print_context):
        ctx = print_context.get_cairo_context()

        print "Context: %d x %d" % (print_context.get_width(),
                                    print_context.get_height())
        print "Size: %d x %d" % (self.size[0], self.size[1])

        factor_x = float(print_context.get_width()) / float(self.size[0])
        factor_y = float(print_context.get_height()) / float(self.size[1])
        factor = min(factor_x, factor_y)

        print "Scale: %f x %f --> %f" % (factor_x, factor_y, factor)
        factor *= 2  # TODO(Jflesch): x2 ???

        ctx.scale(factor, factor)

        self.pdf_page.render_for_printing(ctx)
        return None

