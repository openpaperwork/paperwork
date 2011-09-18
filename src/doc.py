import Image
import codecs
import os
import os.path
import re
import time

import cairo
import gtk
import sane
import PIL

import tesseract
from util import strip_accents

class ScannedDoc(object):
    EXT_TXT = "txt"
    EXT_IMG_SCAN = "bmp"
    EXT_IMG = "jpg"

    SCAN_STEP_SCAN = 0
    SCAN_STEP_OCR = 1

    def __init__(self, docpath, docid = None):
        """
        Arguments:
            docpath --- For an existing document, the path to its folder. For a new one, the rootdir of all documents
            docid --- Document Id (ie folder name). Use None for a new document
        """
        if docid == None:
            self.docid = time.strftime("%Y%m%d_%H%M_%S")
            self.docpath = os.path.join(docpath, self.docid)
        else:
            self.docid = docid
            self.docpath = docpath

    def __str__(self):
        return self.docid

    def get_nb_pages(self):
        # XXX(Jflesch): We try to not make assumptions regarding file names,
        # except regarding their extensions (.txt/.jpg/etc)
        try:
            filelist = os.listdir(self.docpath)
            i = 0
            for f in filelist:
                if f[-4:].lower() != "."+self.EXT_IMG:
                    continue
                i += 1
            return i
        except Exception, e:
            print "Exception while trying to get the number of pages of '%s': %s" % (self.docid, e)
            return 0

    def _get_filepath(self, page, ext):
        assert(page > 0)

        # XXX(Jflesch): We try to not make assumptions regarding file names,
        # except regarding their extensions (.txt/.jpg/etc)

        filelist = os.listdir(self.docpath)
        filelist.sort()
        i = 1
        for f in filelist:
            if f[-4:].lower() != "."+ext:
                continue
            if page == i:
                return os.path.join(self.docpath, f)
            i += 1
        if i == page:
            return os.path.join(self.docpath, "paper.%d.%s" % (page, ext)) # new page
        raise Exception("Page %d not found in document '%s' ! (last: %d)" % (page, self.docid, i))

    def get_txt_path(self, page):
        return self._get_filepath(page, self.EXT_TXT)

    def get_img_path(self, page):
        return self._get_filepath(page, self.EXT_IMG)

    def get_text(self, page):
        txtfile = self.get_txt_path(page)
        txt = ""
        with codecs.open(txtfile, encoding='utf-8') as fd:
            for line in fd.readlines():
                txt += line
        return txt

    def _dummy_callback(step, progression, total):
        pass

    def _scan(self, callback, page):
        """
        Scan a page, and generate 4 output files:
            <docid>/paper.rotate.0.bmp: original output
            <docid>/paper.rotate.1.bmp: original output at 90 degrees
            <docid>/paper.rotate.2.bmp: original output at 180 degrees
            <docid>/paper.rotate.3.bmp: original output at 270 degrees
        OCR will have to decide which is the best
        """
        devices = sane.get_devices()
        if len(devices) == 0:
            # TODO(Jflesch): This warning should be in mainwindow.py
            warn = gtk.MessageDialog(flags = gtk.DIALOG_MODAL,
                                    type = gtk.MESSAGE_WARNING,
                                    buttons = gtk.BUTTONS_OK,
                                    message_format = "No scanner found") # TODO(Jflesch): i18n/l10n
            warn.run()
            warn.destroy()
            raise Exception("No scanner found")
        print "Will use device '%s'" % (str(devices[0]))
        device = sane.open(devices[0][0])
        callback(self.SCAN_STEP_SCAN, 20, 100)
        try:
            try:
                device.resolution = 350
            except AttributeError, e:
                print "WARNING: Can't set scanner resolution: " + e
            try:
                device.mode = 'Color'
            except AttributeError, e:
                print "WARNING: Can't set scanner mode: " + e
            # TODO(Jflesch): call callback
            pic = device.scan()
        except Exception, e:
            print "ERROR while scanning: %s" % (e)
            return
        finally:
            device.close()

        outfiles = []
        for r in range(0, 4):
            imgpath = os.path.join(self.docpath, ("rotated.%d.%s" % (r, self.EXT_IMG_SCAN)))
            print "Saving scan (rotated %d degree) in '%s'" % (r * 90, imgpath)
            pic.save(imgpath)
            outfiles.append(imgpath)
            pic = pic.rotate(90)
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
            callback(self.SCAN_STEP_OCR, i, len(files))
            i += 1
            print "Running OCR on scan '%s'" % (imgpath)
            txt = tesseract.image_to_string(Image.open(imgpath), lang=ocrlang)
            txt = unicode(txt)
            score = self._compute_ocr_score(txt)
            scores.append( (score, imgpath, txt) )

        # Note: we want the higher first
        scores.sort(cmp = lambda x, y: self._compare_score(y[0], x[0]))

        print "Best: %f -> %s" % (scores[0][0], scores[0][1])
        return (scores[0][1], scores[0][2])


    def scan_next_page(self, ocrlang, callback = _dummy_callback):
        try:
            os.makedirs(self.docpath)
        except OSError:
            pass

        page = self.get_nb_pages() + 1 # remember: we start counting from 1

        imgfile = self.get_img_path(page)
        txtfile = self.get_txt_path(page)

        callback(self.SCAN_STEP_SCAN, 0, 100)
        outfiles = self._scan(callback, page)
        callback(self.SCAN_STEP_OCR, 0, 100)
        (bmpfile, txt) = self._ocr(callback, outfiles, ocrlang)

        # Convert the image and save it in its final place
        im = PIL.Image.open(bmpfile)
        im.save(imgfile)

        # Save the text
        with open(txtfile, 'w') as fd:
            fd.write(txt)

        # delete temporary files
        for outfile in outfiles:
            os.unlink(outfile)

        print "Scan done"

    def destroy(self):
        print "Destroying doc: %s" % self.docpath
        for root, dirs, files in os.walk(self.docpath, topdown = False):
            for f in files:
                f = os.path.join(self.docpath, f)
                print "Deleting file %s" % f
                os.unlink(f)
            for d in dirs:
                d = os.path.join(self.docpath, d)
                print "Deleting dir %s" % d
                os.rmdir(d)
        os.rmdir(self.docpath)
        print "Done"

    def draw_page(self, print_op, print_context, page):
        ORIENTATION_PORTRAIT = 0
        ORIENTATION_LANDSCAPE = 1

        imgpath = self.get_img_path(page+1)

        pixbuf = gtk.gdk.pixbuf_new_from_file(imgpath)

        # take care of rotating the image if required
        print "Rotating the page ..."
        if print_context.get_width() <= print_context.get_height():
            print_orientation = ORIENTATION_PORTRAIT
        else:
            print_orientation = ORIENTATION_LANDSCAPE
        if pixbuf.get_width() <= pixbuf.get_height():
            pixbuf_orientation = ORIENTATION_PORTRAIT
        else:
            pixbuf_orientation = ORIENTATION_LANDSCAPE
        if print_orientation != pixbuf_orientation:
            pixbuf = pixbuf.rotate_simple(gtk.gdk.PIXBUF_ROTATE_CLOCKWISE)

        # scale the image down
        # XXX(Jflesch): beware that we get floats for the page size ...
        print "Scaling it down to %fx%f..." % (print_context.get_width(), print_context.get_height())
        pixbuf = pixbuf.scale_simple(int(print_context.get_width()),
                                     int(print_context.get_height()),
                                     gtk.gdk.INTERP_HYPER)

        # .. and print !
        format = cairo.FORMAT_RGB24
        if pixbuf.get_has_alpha():
            format = cairo.FORMAT_ARGB32
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        image = cairo.ImageSurface(format, width, height)

        cr = print_context.get_cairo_context()
        gdkcontext = gtk.gdk.CairoContext(cr)
        gdkcontext.set_source_pixbuf(pixbuf, 0, 0)
        gdkcontext.paint()

