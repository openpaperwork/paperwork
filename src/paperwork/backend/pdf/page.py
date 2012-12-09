#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
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

import cairo
import codecs
import os
import pyocr.builders
import pyocr.pyocr

from paperwork.backend.common.page import BasicPage
from paperwork.util import surface2image


class PdfPage(BasicPage):
    FILE_PREFIX = "paper."
    EXT_TXT = "txt"
    EXT_BOX = "words"

    def __init__(self, doc, page_nb):
        BasicPage.__init__(self, doc, page_nb)
        self.pdf_page = doc.pdf.get_page(page_nb)
        size = self.pdf_page.get_size()
        self.size = (int(size[0]), int(size[1]))

    def __get_filepath(self, ext):
        """
        Returns a file path relative to this page
        """
        return os.path.join(self.doc.path,
                "%s%d.%s" % (self.FILE_PREFIX, self.page_nb + 1, ext))

    def __get_txt_path(self):
        return self.__get_filepath(self.EXT_TXT)

    def __get_box_path(self):
        return self.__get_filepath(self.EXT_BOX)

    def __get_text(self):
        txtfile = self.__get_txt_path()

        try:
            os.stat(txtfile)

            txt = []
            try:
                with codecs.open(txtfile, 'r', encoding='utf-8') as file_desc:
                    for line in file_desc.readlines():
                        line = line.strip()
                        txt.append(line)
            except IOError, exc:
                print "Unable to read [%s]: %s" % (txtfile, str(exc))
            return txt

        except OSError, exc:  # os.stat() failed
            txt = self.pdf_page.get_text()
            txt = unicode(txt, errors='replace')
            return txt.split(u"\n")

    text = property(__get_text)

    def __get_boxes(self):
        """
        Get all the word boxes of this page.
        """
        boxfile = self.__get_box_path()
        txt = self.text

        try:
            os.stat(boxfile)

            box_builder = pyocr.builders.WordBoxBuilder()

            try:
                with codecs.open(boxfile, 'r', encoding='utf-8') as file_desc:
                    boxes = box_builder.read_file(file_desc)
                return boxes
            except IOError, exc:
                print "Unable to get boxes for '%s': %s" % (self.doc.docid, exc)
                return []
        except OSError, exc:  # os.stat() failed
            # TODO(Jflesch): Can't find poppler.Page.get_text_layout() ?
            pass
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

    def redo_ocr(self, ocrlang):
        img = self.img
        txtfile = self.__get_txt_path()
        boxfile = self.__get_box_path()

        ocr_tools = pyocr.pyocr.get_available_tools()
        if len(ocr_tools) <= 0:
            # shouldn't happen: scan buttons should be disabled
            # in that case
            raise Exception("No OCR tool available")

        txt = ocr_tools[0].image_to_string(img, lang=ocrlang)
        boxes = ocr_tools[0].image_to_string(img, lang=ocrlang,
                                             builder=pyocr.builders.WordBoxBuilder())

        # save the text
        with open(txtfile, 'w') as file_desc:
            file_desc.write(txt)
        # save the boxes
        with open(boxfile, 'w') as file_desc:
            pyocr.builders.WordBoxBuilder.write_file(file_desc, boxes)

