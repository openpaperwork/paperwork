#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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
import itertools
import os
import logging
import pyocr
import pyocr.builders

from ..common.page import BasicPage
from ..util import surface2image


# By default, PDF are too small for a good image rendering
# so we increase their size
PDF_RENDER_FACTOR = 4
logger = logging.getLogger(__name__)


def minmax_rects(rects):
    (mx1, my1, mx2, my2) = (6553600000, 6553600000, 0, 0)
    for rectangle in rects:
        ((x1, y1), (x2, y2)) = (
            (int(rectangle.x1 * PDF_RENDER_FACTOR),
             int(rectangle.y2 * PDF_RENDER_FACTOR)),
            (int(rectangle.x2 * PDF_RENDER_FACTOR),
             int(rectangle.y1 * PDF_RENDER_FACTOR))
        )
        (x1, x2) = (min(x1, x2), max(x1, x2))
        (y1, y2) = (min(y1, y2), max(y1, y2))
        mx1 = min(mx1, x1)
        my1 = min(my1, y1)
        mx2 = max(mx2, x2)
        my2 = max(my2, y2)
    rect = ((mx1, my1), (mx2, my2))
    return rect


class PdfWordBox(object):
    def __init__(self, content, position):
        self.content = content
        self.position = minmax_rects(position)


class PdfLineBox(object):
    def __init__(self, word_boxes, position):
        self.word_boxes = word_boxes
        self.position = minmax_rects(position)

    def _get_content(self):
        return " ".join([w.content for w in self.word_boxes])

    content = property(_get_content)


def custom_split(input_str, input_rects, splitter):
    assert(len(input_str) == len(input_rects))
    input_el = zip(input_str, input_rects)
    for (is_split, group) in itertools.groupby(
        input_el,
        lambda x: splitter(x[0])
    ):
        if is_split:
            continue
        letters = ""
        rects = []
        for (letter, rect) in group:
            letters += letter
            rects.append(rect)
        yield(letters, rects)


class PdfPage(BasicPage):
    EXT_TXT = "txt"

    def __init__(self, doc, pdf, page_nb):
        super().__init__(doc, page_nb)
        self._pdf_page = None
        size = self.pdf_page.get_size()
        self._size = (int(size[0]), int(size[1]))
        self.__boxes = None
        self.__img_cache = {}

    @property
    def pdf_page(self):
        if self._pdf_page:
            return self._pdf_page
        self._pdf_page = self.doc.pdf.get_page(self.page_nb)
        return self._pdf_page

    def drop_cache(self):
        super().drop_cache()
        if self._pdf_page:
            del self._pdf_page
        self._pdf_page = None

    def get_doc_file_path(self):
        """
        Returns the file path of the image corresponding to this page
        """
        return self.doc.get_pdf_file_path()

    def __get_txt_path(self):
        return self._get_filepath(self.EXT_TXT)

    def __get_box_path(self):
        return self._get_filepath(self.EXT_BOX)

    def __get_last_mod(self):
        try:
            return os.stat(self.__get_box_path()).st_mtime
        except OSError:
            return 0.0

    last_mod = property(__get_last_mod)

    def _get_text(self):
        txtfile = self.__get_txt_path()

        try:
            os.stat(txtfile)

            txt = []
            try:
                with codecs.open(txtfile, 'r', encoding='utf-8') as file_desc:
                    for line in file_desc.readlines():
                        line = line.strip()
                        txt.append(line)
            except IOError as exc:
                logger.error("Unable to read [%s]: %s" % (txtfile, str(exc)))
            return txt

        except OSError as exc:  # os.stat() failed
            pass

        boxfile = self.__get_box_path()
        try:
            os.stat(boxfile)

            # reassemble text based on boxes
            boxes = self.boxes
            txt = []
            for line in boxes:
                txt_line = u""
                for box in line.word_boxes:
                    txt_line += u" " + box.content
                txt.append(txt_line)
            return txt
        except OSError as exc:
            txt = self.pdf_page.get_text()
            return txt.split(u"\n")

    def __get_boxes(self):
        """
        Get all the word boxes of this page.
        """
        if self.__boxes is not None:
            return self.__boxes

        # Check first if there is an OCR file available
        boxfile = self.__get_box_path()
        try:
            os.stat(boxfile)

            box_builder = pyocr.builders.LineBoxBuilder()

            try:
                with codecs.open(boxfile, 'r', encoding='utf-8') as file_desc:
                    self.__boxes = box_builder.read_file(file_desc)
                return self.__boxes
            except IOError as exc:
                logger.error("Unable to get boxes for '%s': %s"
                             % (self.doc.docid, exc))
                # will fall back on pdf boxes
        except OSError as exc:  # os.stat() failed
            pass

        # fall back on what libpoppler tells us

        txt = self.pdf_page.get_text()
        self.__boxes = []

        layout = self.pdf_page.get_text_layout()
        if not layout[0]:
            layout = []
            return self.__boxes
        layout = layout[1]

        for (line, line_rects) in custom_split(
            txt, layout, lambda x: x == "\n"
        ):
            words = []
            for (word, word_rects) in custom_split(
                line, line_rects, lambda x: x.isspace()
            ):
                word_box = PdfWordBox(word, word_rects)
                words.append(word_box)
            line_box = PdfLineBox(words, line_rects)
            self.__boxes.append(line_box)
        return self.__boxes

    def __set_boxes(self, boxes):
        boxfile = self.__get_box_path()
        with codecs.open(boxfile, 'w', encoding='utf-8') as file_desc:
            pyocr.builders.LineBoxBuilder().write_file(file_desc, boxes)
        self.drop_cache()
        self.doc.drop_cache()

    boxes = property(__get_boxes, __set_boxes)

    def __render_img(self, size):
        # TODO(Jflesch): In a perfect world, we shouldn't use ImageSurface.
        # we should draw directly on the GtkImage.window.cairo_create()
        # context. It would be much more efficient.

        logger.debug('Building img from pdf: {}'.format(size))
        width = int(size[0])
        height = int(size[1])
        factor_w = width / self._size[0]
        factor_h = height / self._size[1]

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)
        ctx.scale(factor_w, factor_h)
        self.pdf_page.render(ctx)
        return surface2image(surface)

    def __get_img(self):
        return self.__render_img(
            (self._size[0] * PDF_RENDER_FACTOR,
             self._size[1] * PDF_RENDER_FACTOR)
        )

    img = property(__get_img)

    def get_image(self, size):
        return self.__render_img(size)

    def get_thumbnail(self, width, height):
        # use only the on-disk cache if it's the page 0 (used in the document
        # list)
        # otherwise, it's either to just generate the image
        if self.page_nb == 0:
            return super().get_thumbnail(width, height)
        return self.get_image((width, height))

    def __get_size(self):
        # default size
        return (self._size[0] * PDF_RENDER_FACTOR,
                self._size[1] * PDF_RENDER_FACTOR)

    size = property(__get_size)

    def print_page_cb(self, print_op, print_context, keep_refs={}):
        ctx = print_context.get_cairo_context()

        logger.debug("Context: %d x %d" % (print_context.get_width(),
                                           print_context.get_height()))
        logger.debug("Size: %d x %d" % (self._size[0], self._size[1]))

        factor_x = float(print_context.get_width()) / float(self._size[0])
        factor_y = float(print_context.get_height()) / float(self._size[1])
        factor = min(factor_x, factor_y)

        logger.debug("Scale: %f x %f --> %f" % (factor_x, factor_y, factor))

        ctx.scale(factor, factor)

        self.pdf_page.render_for_printing(ctx)
        return None
