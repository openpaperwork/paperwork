import codecs
import Image
import ImageDraw
import os
import os.path
import re
import time

import cairo
import gtk
import PIL

import tesseract
from util import strip_accents

class ScannedPage(object):
    EXT_TXT = "txt"
    EXT_BOX = "box"
    EXT_IMG_SCAN = "bmp"
    EXT_IMG = "jpg"

    SCAN_STEP_SCAN = 0
    SCAN_STEP_OCR = 1

    def __init__(self, doc, page_nb):
        """
        Don't create directly. Please use ScannedDoc.get_page()
        """
        self.doc = doc
        self.page = page_nb
        assert(self.page > 0)

    def _get_filepath(self, ext):
        return os.path.join(self.doc.docpath, "paper.%d.%s" % (self.page, ext)) # new page

    def _get_txt_path(self):
        return self._get_filepath(self.EXT_TXT)

    def _get_box_path(self):
        return self._get_filepath(self.EXT_BOX)

    def _get_img_path(self):
        return self._get_filepath(self.EXT_IMG)

    def get_text(self):
        txtfile = self._get_txt_path()
        txt = ""
        with codecs.open(txtfile, encoding='utf-8') as fd:
            for line in fd.readlines():
                txt += line
        return txt

    def get_boxes(self):
        boxfile = self._get_box_path()
        try:
            with open(boxfile) as fd:
                boxes = tesseract.read_boxes(fd)
            return boxes
        except Exception, e:
            print "Unable to get boxes for '%s': %s" % (self.docid, e)
            return []

    def get_normal_img(self):
        return Image.open(self._get_img_path())

    def get_boxed_img(self, keywords):
        img = self.get_normal_img()
        boxes = self.get_boxes()

        draw = ImageDraw.Draw(img)
        for box in boxes:
            # TODO(Jflesch): add highlights
            draw.rectangle(box.get_xy(), outline = (0x00, 0x00, 0xFF))

        return img

    def _scan(self, device, callback):
        """
        Scan a page, and generate 4 output files:
            <docid>/paper.rotated.0.bmp: original output
            <docid>/paper.rotated.1.bmp: original output at 90 degrees
        OCR will have to decide which is the best
        """
        callback(self.SCAN_STEP_SCAN, 0, 100)
        try:
            # TODO(Jflesch): call callback
            pic = device.scan()
        except Exception, e:
            print "ERROR while scanning: %s" % (e)
            return []

        outfiles = []
        for r in range(0, 2):
            imgpath = os.path.join(self.doc.docpath, ("rotated.%d.%s" % (r, self.EXT_IMG_SCAN)))
            print "Saving scan (rotated %d degree) in '%s'" % (r * -90, imgpath)
            pic.save(imgpath)
            outfiles.append(imgpath)
            pic = pic.rotate(-90)
        return outfiles

    def _compute_ocr_score(self, txt):
        """
        Try to evaluate how well the OCR worked.
        Current implementation:
            The score is the number of words only made of 4 or more letters ([a-zA-Z])
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

    def _compare_score(self, x, y):
        if ( x < y ):
            return -1
        elif ( x > y ):
            return 1
        else:
            return 0

    def _ocr(self, callback, files, ocrlang):
        scores = []

        i = 0
        for imgpath in files:
            callback(self.SCAN_STEP_OCR, i, len(files)+1)
            i += 1
            print "Running OCR on scan '%s'" % (imgpath)
            txt = tesseract.image_to_string(Image.open(imgpath), lang=ocrlang)
            txt = unicode(txt)
            score = self._compute_ocr_score(txt)
            scores.append( (score, imgpath, txt) )

        # Note: we want the higher first
        scores.sort(cmp = lambda x, y: self._compare_score(y[0], x[0]))

        print "Best: %f -> %s" % (scores[0][0], scores[0][1])

        print "Extracting boxes ..."
        callback(self.SCAN_STEP_OCR, i, len(files)+1)
        boxes = tesseract.image_to_string(Image.open(imgpath), lang=ocrlang, boxes=True)
        print "Done"

        return (scores[0][1], scores[0][2], boxes)

    def scan_page(self, device, ocrlang, callback):
        imgfile = self._get_img_path()
        txtfile = self._get_txt_path()
        boxfile = self._get_box_path()

        callback(self.SCAN_STEP_SCAN, 0, 100)
        outfiles = self._scan(device, callback)
        callback(self.SCAN_STEP_OCR, 0, 100)
        (bmpfile, txt, boxes) = self._ocr(callback, outfiles, ocrlang)

        # Convert the image and save it in its final place
        im = PIL.Image.open(bmpfile)
        im.save(imgfile)

        # Save the text
        with open(txtfile, 'w') as fd:
            fd.write(txt)

        # Save the boxes
        with open(boxfile, 'w') as fd:
            tesseract.write_box_file(fd, boxes)

        # delete temporary files
        for outfile in outfiles:
            os.unlink(outfile)

        print "Scan done"

    def print_page(self, print_op, print_context,):
        """
        Called for printing operation by Gtk
        """
        ORIENTATION_PORTRAIT = 0
        ORIENTATION_LANDSCAPE = 1

        # By default, the context is using 72 dpi, which is by far not enough
        # --> we change it to 300 dpi
        print_context.set_cairo_context(print_context.get_cairo_context(), 300, 300)

        imgpath = self._get_img_path()

        pixbuf = gtk.gdk.pixbuf_new_from_file(imgpath)

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
        print "DPI: %fx%f" % (print_context.get_dpi_x(), print_context.get_dpi_y())
        print "Scaling it down to %fx%f..." % (new_w, new_h)
        pixbuf = pixbuf.scale_simple(new_w, new_h, gtk.gdk.INTERP_BILINEAR)

        # .. and print !
        cr = print_context.get_cairo_context()
        gdkcontext = gtk.gdk.CairoContext(cr)
        gdkcontext.set_source_pixbuf(pixbuf, left_margin, top_margin)
        gdkcontext.paint()

    def get_page_nb(self):
        """
        Indicates which page number this page has. Beware that page numbers
        starts at 1 here !
        """
        return self.page

    def __str__(self):
        return "%s p%d" % (str(self.doc), self.page)


