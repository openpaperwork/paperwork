"""
Code relative to page handling.
"""

import codecs
from copy import copy
import Image
import os
import os.path
import re

import gtk
import pyocr.builders
import pyocr.pyocr

from paperwork.backend.common.page import BasicPage
from paperwork.backend.common.page import PageExporter
from paperwork.backend.config import PaperworkConfig
from paperwork.util import dummy_progress_cb
from paperwork.util import split_words


class ImgPage(BasicPage):
    """
    Represents a page. A page is a sub-element of ImgDoc.
    """
    FILE_PREFIX = "paper."
    EXT_TXT = "txt"
    EXT_BOX = "words"
    EXT_IMG_SCAN = "bmp"
    EXT_IMG = "jpg"

    KEYWORD_HIGHLIGHT = 3

    PRINT_RESOLUTION = 150  # dpi

    ORIENTATION_PORTRAIT = 0
    ORIENTATION_LANDSCAPE = 1


    def __init__(self, doc, page_nb):
        BasicPage.__init__(self, doc, page_nb)

    def __get_filepath(self, ext):
        """
        Returns a file path relative to this page
        """
        return os.path.join(self.doc.path,
                "%s%d.%s" % (self.FILE_PREFIX, self.page_nb + 1, ext))

    def __get_txt_path(self):
        """
        Returns the file path of the text corresponding to this page
        """
        return self.__get_filepath(self.EXT_TXT)

    __txt_path = property(__get_txt_path)

    def __get_box_path(self):
        """
        Returns the file path of the box list corresponding to this page
        """
        return self.__get_filepath(self.EXT_BOX)

    __box_path = property(__get_box_path)

    def __get_img_path(self):
        """
        Returns the file path of the image corresponding to this page
        """
        return self.__get_filepath(self.EXT_IMG)

    __img_path = property(__get_img_path)

    def __get_text(self):
        """
        Get the text corresponding to this page
        """
        txtfile = self.__txt_path
        txt = []
        try:
            with codecs.open(txtfile, 'r', encoding='utf-8') as file_desc:
                for line in file_desc.readlines():
                    line = line.strip()
                    txt.append(line)
        except IOError, exc:
            print "Unable to read [%s]: %s" % (txtfile, str(exc))
        return txt

    text = property(__get_text)

    def __get_boxes(self):
        """
        Get all the word boxes of this page.
        """
        boxfile = self.__box_path
        txt = self.text

        box_builder = pyocr.builders.WordBoxBuilder()

        try:
            with codecs.open(boxfile, 'r', encoding='utf-8') as file_desc:
                boxes = box_builder.read_file(file_desc)
            return boxes
        except IOError, exc:
            print "Unable to get boxes for '%s': %s" % (self.doc.docid, exc)
            return []

    boxes = property(__get_boxes)

    def __get_img(self):
        """
        Returns an image object corresponding to the page
        """
        return Image.open(self.__img_path)

    img = property(__get_img)

    def get_thumbnail(self, width):
        img = self.img
        (w, h) = img.size
        factor = (float(w) / width)
        w = width
        h /= factor
        img = img.resize((int(w), int(h)))
        return img

    def __save_imgs(self, img, scan_res=0, scanner_calibration=None,
                    callback=dummy_progress_cb):
        """
        Make a page (on disk), and generate 4 output files:
            <docid>/paper.rotated.0.bmp: original output
            <docid>/paper.rotated.1.bmp: original output at 90 degrees
        OCR will have to decide which is the best
        """
        print "Scanner resolution: %d" % (scan_res)
        print "Scanner calibration: %s" % (str(scanner_calibration))
        print ("Calibration resolution: %d" %
               (PaperworkConfig.CALIBRATION_RESOLUTION))
        if scan_res != 0 and scanner_calibration != None:
            cropping = (scanner_calibration[0][0]
                        * scan_res
                        / PaperworkConfig.CALIBRATION_RESOLUTION,
                        scanner_calibration[0][1]
                        * scan_res
                        / PaperworkConfig.CALIBRATION_RESOLUTION,
                        scanner_calibration[1][0]
                        * scan_res
                        / PaperworkConfig.CALIBRATION_RESOLUTION,
                        scanner_calibration[1][1]
                        * scan_res
                        / PaperworkConfig.CALIBRATION_RESOLUTION)
            print "Cropping: %s" % (str(cropping))
            img = img.crop(cropping)

        # strip the alpha channel if there is one
        color_channels = img.split()
        img = Image.merge("RGB", color_channels[:3])

        outfiles = []
        for rotation in range(0, 2):
            imgpath = os.path.join(self.doc.path,
                    ("rotated.%d.%s" % (rotation, self.EXT_IMG_SCAN)))
            print ("Saving scan (rotated %d degree) in '%s'"
                   % (rotation * -90, imgpath))
            img.save(imgpath)
            outfiles.append(imgpath)
            img = img.rotate(-90)
        return outfiles

    @staticmethod
    def __compute_ocr_score(txt):
        """
        Try to evaluate how well the OCR worked.
        Current implementation:
            The score is the number of words only made of 4 or more letters
            ([a-zA-Z])
        """
        # TODO(Jflesch): i18n / l10n
        score = 0
        prog = re.compile(r'^[a-zA-Z]{4,}$')
        for word in txt.split(" "):
            if prog.match(word):
                score += 1
        print "---"
        print txt
        print "---"
        print "Got score of %d" % (score)
        return score

    @staticmethod
    def __compare_score(score_x, score_y):
        """
        Compare scores

        Returns:
            -1 : if X is lower than Y
            1 : if X is higher than Y
            0 : if both are equal
        """
        if score_x < score_y:
            return -1
        elif score_x > score_y:
            return 1
        else:
            return 0

    def __ocr(self, files, ocrlang, callback=dummy_progress_cb):
        """
        Do the OCR on the page
        """
        ocr_tools = pyocr.pyocr.get_available_tools()
        if len(ocr_tools) <= 0:
            # shouldn't happen: scan buttons should be disabled
            # in that case
            raise Exception("No OCR tool available")

        print "Using %s for OCR" % (ocr_tools[0].get_name())

        scores = []

        i = 0
        for imgpath in files:
            callback(i, len(files) + 1, self.SCAN_STEP_OCR)
            i += 1
            print "Running OCR on scan '%s'" % (imgpath)
            txt = ocr_tools[0].image_to_string(Image.open(imgpath), lang=ocrlang)
            txt = unicode(txt)
            score = self.__compute_ocr_score(txt)
            scores.append((score, imgpath, txt))

        # Note: we want the higher first
        scores.sort(cmp=lambda x, y: self.__compare_score(y[0], x[0]))

        print "Best: %f -> %s" % (scores[0][0], scores[0][1])

        print "Extracting boxes ..."
        callback(i, len(files) + 1, self.SCAN_STEP_OCR)
        boxes = ocr_tools[0].image_to_string(Image.open(scores[0][1]),
                lang=ocrlang, builder=pyocr.builders.WordBoxBuilder())
        print "Done"

        return (scores[0][1], scores[0][2], boxes)

    def make(self, img, ocrlang, scan_res=0, scanner_calibration=None,
                  callback=dummy_progress_cb):
        """
        Scan the page & do OCR
        """
        imgfile = self.__img_path
        txtfile = self.__txt_path
        boxfile = self.__box_path

        callback(0, 100, self.SCAN_STEP_SCAN)
        outfiles = self.__save_imgs(img, scan_res, scanner_calibration,
                                    callback)
        callback(0, 100, self.SCAN_STEP_OCR)
        (bmpfile, txt, boxes) = self.__ocr(outfiles, ocrlang, callback)

        # Convert the image and save it in its final place
        img = Image.open(bmpfile)
        img.save(imgfile)

        # Save the text
        with open(txtfile, 'w') as file_desc:
            file_desc.write(txt)

        # Save the boxes
        with open(boxfile, 'w') as file_desc:
            pyocr.builders.WordBoxBuilder().write_file(file_desc, boxes)

        # delete temporary files
        for outfile in outfiles:
            os.unlink(outfile)

        print "Scan done"

    def print_page_cb(self, print_op, print_context):
        """
        Called for printing operation by Gtk
        """
        # By default, the context is using 72 dpi, which is by far not enough
        # --> we change it to PRINT_RESOLUTION dpi
        print_context.set_cairo_context(print_context.get_cairo_context(),
                                        self.PRINT_RESOLUTION,
                                        self.PRINT_RESOLUTION)

        pixbuf = gtk.gdk.pixbuf_new_from_file(self.__img_path)

        # take care of rotating the image if required
        if print_context.get_width() <= print_context.get_height():
            print_orientation = self.ORIENTATION_PORTRAIT
        else:
            print_orientation = self.ORIENTATION_LANDSCAPE
        if pixbuf.get_width() <= pixbuf.get_height():
            pixbuf_orientation = self.ORIENTATION_PORTRAIT
        else:
            pixbuf_orientation = self.ORIENTATION_LANDSCAPE
        if print_orientation != pixbuf_orientation:
            print "Rotating the page ..."
            pixbuf = pixbuf.rotate_simple(gtk.gdk.PIXBUF_ROTATE_CLOCKWISE)

        # scale the image down
        # XXX(Jflesch): beware that we get floats for the page size ...
        page_setup = print_context.get_page_setup()
        top_margin = (int(print_context.get_height())
                      * (page_setup.get_top_margin(gtk.UNIT_POINTS)
                         / page_setup.get_paper_height(gtk.UNIT_POINTS)))
        bottom_margin = (int(print_context.get_height())
                      * (page_setup.get_bottom_margin(gtk.UNIT_POINTS)
                         / page_setup.get_paper_height(gtk.UNIT_POINTS)))
        left_margin = (int(print_context.get_width())
                      * (page_setup.get_left_margin(gtk.UNIT_POINTS)
                         / page_setup.get_paper_width(gtk.UNIT_POINTS)))
        right_margin = (int(print_context.get_width())
                      * (page_setup.get_right_margin(gtk.UNIT_POINTS)
                         / page_setup.get_paper_width(gtk.UNIT_POINTS)))

        new_w = int(print_context.get_width() - left_margin - right_margin)
        new_h = int(print_context.get_height() - top_margin - bottom_margin)
        print "DPI: %fx%f" % (print_context.get_dpi_x(),
                              print_context.get_dpi_y())
        print "Scaling it down to %fx%f..." % (new_w, new_h)
        pixbuf = pixbuf.scale_simple(new_w, new_h, gtk.gdk.INTERP_BILINEAR)

        # .. and print !
        cairo_context = print_context.get_cairo_context()
        gdkcontext = gtk.gdk.CairoContext(cairo_context)
        gdkcontext.set_source_pixbuf(pixbuf, left_margin, top_margin)
        gdkcontext.paint()

    def redo_ocr(self, ocrlang):
        """
        Rerun the OCR on the document

        Arguments:
            ocrlang --- lang to specify to the OCR tool
        """
        print "Redoing OCR of '%s'" % (str(self))

        imgfile = self.__img_path
        txtfile = self.__txt_path
        boxfile = self.__box_path

        (imgfile, txt, boxes) = self.__ocr([imgfile], ocrlang,
                                           dummy_progress_cb)
        # save the text
        with open(txtfile, 'w') as file_desc:
            file_desc.write(txt)
        # save the boxes
        with open(boxfile, 'w') as file_desc:
            pyocr.builders.WordBoxBuilder.write_file(file_desc, boxes)

    def __ch_number(self, offset):
        """
        Move the page number by a given offset. Beware to not let any hole
        in the page numbers when doing this. Make sure also that the wanted
        number is available.
        Will also change the page number of the current object.
        """
        src = {}
        src["txt"] = self.__get_txt_path()
        src["box"] = self.__get_box_path()
        src["img"] = self.__get_img_path()

        self.page_nb += offset

        dst = {}
        dst["txt"] = self.__get_txt_path()
        dst["box"] = self.__get_box_path()
        dst["img"] = self.__get_img_path()

        for key in src.keys():
            if os.access(src[key], os.F_OK):
                os.rename(src[key], dst[key])

    def destroy(self):
        """
        Delete the page. May delete the whole document if it's actually the
        last page.
        """
        print "Destroying page: %s" % self
        if self.doc.nb_pages <= 1:
            self.doc.destroy()
            return
        current_doc_nb_pages = self.doc.nb_pages
        if os.access(self.__get_txt_path(), os.F_OK):
            os.unlink(self.__get_txt_path())
        if os.access(self.__get_box_path(), os.F_OK):
            os.unlink(self.__get_box_path())
        if os.access(self.__get_img_path(), os.F_OK):
            os.unlink(self.__get_img_path())
        for page_nb in range(self.page_nb + 1, current_doc_nb_pages):
            page = self.doc.pages[page_nb]
            page.__ch_number(-1)

