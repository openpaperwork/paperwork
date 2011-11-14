"""
Code relative to page handling.
"""

import codecs
import Image
import ImageDraw
import os
import os.path
import re

import gtk
import PIL

import tesseract
from util import dummy_progress_cb
from util import strip_accents
from util import SPLIT_KEYWORDS_REGEX
from wordbox import get_word_boxes


class ScannedPage(object):
    """
    Represents a page. A page is a sub-element of ScannedDoc.
    """
    FILE_PREFIX = "paper."
    EXT_TXT = "txt"
    EXT_BOX = "box"
    EXT_IMG_SCAN = "bmp"
    EXT_IMG = "jpg"

    SCAN_STEP_SCAN = "scanning"
    SCAN_STEP_OCR = "ocr"

    KEYWORD_HIGHLIGHT = 3

    PRINT_RESOLUTION = 150  # dpi

    def __init__(self, doc, page_nb):
        """
        Don't create directly. Please use ScannedDoc.get_page()
        """
        self.doc = doc
        self.page_nb = page_nb
        assert(self.page_nb >= 0)

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
            with codecs.open(txtfile, encoding='utf-8') as file_desc:
                for line in file_desc.readlines():
                    line = line.strip()
                    txt.append(line)
        except IOError, exc:
            print "Unable to read [%s]: %s" % (txtfile, str(exc))
        return txt

    text = property(__get_text)

    def get_boxes(self, callback=dummy_progress_cb):
        """
        Get all the word boxes of this page. Note that this process may take
        some time (usually 1 to 3 seconds). This is why this is not a property,
        and this is why this function accept a progression callback argument.
        """
        boxfile = self.__box_path
        txt = self.text

        try:
            with open(boxfile) as file_desc:
                char_boxes = tesseract.read_boxes(file_desc)
            word_boxes = get_word_boxes(txt, char_boxes, callback)
            return word_boxes
        except IOError, exc:
            print "Unable to get boxes for '%s': %s" % (self.doc.docid, exc)
            return []

    def __get_img(self):
        """
        Returns an image object corresponding to the page
        """
        return Image.open(self.__img_path)

    img = property(__get_img)

    @staticmethod
    def __draw_box(draw, img_size, box, width, color):
        """
        Draw a single box. See draw_boxes()
        """
        for i in range(2, width + 2):
            ((pt_a_x, pt_a_y), (pt_b_x, pt_b_y)) = box.position
            pt_a_y = img_size[1] - pt_a_y
            pt_b_y = img_size[1] - pt_b_y
            draw.rectangle(((pt_a_x - i, pt_a_y + i),
                            (pt_b_x + i, pt_b_y - i)),
                           outline=color)

    @staticmethod
    def draw_boxes(img, boxes, color, width, keywords=None):
        """
        Draw the boxes on the image

        Arguments:
            img --- the image
            boxes --- see ScannedPage.boxes
            color --- a tuple of 3 integers (each of them being 0 < X < 256)
             indicating the color to use to draw the boxes
            width --- Width of the line of the boxes
            keywords --- only draw the boxes for these keywords (None == all
                the boxes)
        """
        draw = ImageDraw.Draw(img)
        for box in boxes:
            if (keywords == None or
                strip_accents(box.word.lower().strip()) in keywords):
                ScannedPage.__draw_box(draw, img.size, box, width, color)
        return img

    def __scan(self, device, scanner_calibration, callback=dummy_progress_cb):
        """
        Scan a page, and generate 4 output files:
            <docid>/paper.rotated.0.bmp: original output
            <docid>/paper.rotated.1.bmp: original output at 90 degrees
        OCR will have to decide which is the best
        """
        if scanner_calibration != None:
            cropping = (scanner_calibration[0][0]
                        * device.selected_resolution
                        / device.CALIBRATION_RESOLUTION,
                        scanner_calibration[0][1]
                        * device.selected_resolution
                        / device.CALIBRATION_RESOLUTION,
                        scanner_calibration[1][0]
                        * device.selected_resolution
                        / device.CALIBRATION_RESOLUTION,
                        scanner_calibration[1][1]
                        * device.selected_resolution
                        / device.CALIBRATION_RESOLUTION)
        else:
            cropping = None

        callback(0, 100, self.SCAN_STEP_SCAN)

        # TODO(Jflesch): call callback during the scan
        pic = device.scan()
        if cropping:
            pic = pic.crop(cropping)

        outfiles = []
        for rotation in range(0, 2):
            imgpath = os.path.join(self.doc.path,
                    ("rotated.%d.%s" % (rotation, self.EXT_IMG_SCAN)))
            print ("Saving scan (rotated %d degree) in '%s'"
                   % (rotation * -90, imgpath))
            pic.save(imgpath)
            outfiles.append(imgpath)
            pic = pic.rotate(-90)
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
        scores = []

        i = 0
        for imgpath in files:
            callback(i, len(files) + 1, self.SCAN_STEP_OCR)
            i += 1
            print "Running OCR on scan '%s'" % (imgpath)
            txt = tesseract.image_to_string(Image.open(imgpath), lang=ocrlang)
            txt = unicode(txt)
            score = self.__compute_ocr_score(txt)
            scores.append((score, imgpath, txt))

        # Note: we want the higher first
        scores.sort(cmp=lambda x, y: self.__compare_score(y[0], x[0]))

        print "Best: %f -> %s" % (scores[0][0], scores[0][1])

        print "Extracting boxes ..."
        callback(i, len(files) + 1, self.SCAN_STEP_OCR)
        boxes = tesseract.image_to_string(Image.open(scores[0][1]),
                                          lang=ocrlang, boxes=True)
        print "Done"

        return (scores[0][1], scores[0][2], boxes)

    def scan_page(self, device, ocrlang, scanner_calibration, callback=dummy_progress_cb):
        """
        Scan the page & do OCR
        """
        imgfile = self.__img_path
        txtfile = self.__txt_path
        boxfile = self.__box_path

        callback(0, 100, self.SCAN_STEP_SCAN)
        outfiles = self.__scan(device, scanner_calibration, callback)
        callback(0, 100, self.SCAN_STEP_OCR)
        (bmpfile, txt, boxes) = self.__ocr(outfiles, ocrlang, callback)

        # Convert the image and save it in its final place
        img = PIL.Image.open(bmpfile)
        img.save(imgfile)

        # Save the text
        with open(txtfile, 'w') as file_desc:
            file_desc.write(txt)

        # Save the boxes
        with open(boxfile, 'w') as file_desc:
            tesseract.write_box_file(file_desc, boxes)

        # delete temporary files
        for outfile in outfiles:
            os.unlink(outfile)

        print "Scan done"

    def print_page_cb(self, print_op, print_context):
        """
        Called for printing operation by Gtk
        """
        ORIENTATION_PORTRAIT = 0
        ORIENTATION_LANDSCAPE = 1

        # By default, the context is using 72 dpi, which is by far not enough
        # --> we change it to PRINT_RESOLUTION dpi
        print_context.set_cairo_context(print_context.get_cairo_context(),
                                        self.PRINT_RESOLUTION,
                                        self.PRINT_RESOLUTION)

        pixbuf = gtk.gdk.pixbuf_new_from_file(self.__img_path)

        # take care of rotating the image if required
        if print_context.get_width() <= print_context.get_height():
            print_orientation = ORIENTATION_PORTRAIT
        else:
            print_orientation = ORIENTATION_LANDSCAPE
        if pixbuf.get_width() <= pixbuf.get_height():
            pixbuf_orientation = ORIENTATION_PORTRAIT
        else:
            pixbuf_orientation = ORIENTATION_LANDSCAPE
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

    def __get_keywords(self):
        """
        Get all the keywords related of this page

        Returns:
            An array of strings
        """
        words = []
        for line in self.text:
            for word in SPLIT_KEYWORDS_REGEX.split(line):   # TODO: i18n/l10n
                words.append(word)
        return words

    keywords = property(__get_keywords)

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
            tesseract.write_box_file(file_desc, boxes)

    def ch_number(self, offset):
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
        for p in range(self.page_nb+1, current_doc_nb_pages):
            page = self.doc.pages[p]
            page.ch_number(-1)

    def __str__(self):
        return "%s p%d" % (str(self.doc), self.page_nb + 1)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if None == other:
            return False
        return self.doc == other.doc and self.page_nb == other.page_nb
