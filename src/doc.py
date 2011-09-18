import codecs
import os
import os.path
import sane
import time

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
        raise Exception("Page %d not found in document '%s' !" % (page, self.docid))

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
            <docid>/paper.<page>.rotate.0.bmp: original output
            <docid>/paper.<page>.rotate.1.bmp: original output at 90 degrees
            <docid>/paper.<page>.rotate.2.bmp: original output at 180 degrees
            <docid>/paper.<page>.rotate.3.bmp: original output at 270 degrees
        OCR will have to decide which is the best
        """
        devices = sane.get_devices()
        print "Will use device '%s'" % (str(devices[0]))
        device = sane.open(devices[0][0])
        try:
            try:
                device.resolution = 350
            except AttributeError, e:
                print "WARNING: Can't set scanner resolution: " + e
            try:
                device.mode = 'Color'
            except AttributeError, e:
                print "WARNING: Can't set scanner mode: " + e

            pic = device.scan()
        except Exception, e:
            print "ERROR while scanning: %s" % (e)
            return
        finally:
            device.close()

        for r in range(0, 4):
            imgpath = self._get_filepath(page, ("rotated.%d.%s" % (r, self.EXT_IMG_SCAN)))
            print "Saving scan (rotated %d degree) in '%s'" % (r * 90, imgpath)
            pic.save(imgpath)
            pic = pic.rotate(90)

    def _ocr(self, callback, page):
        pass

    def scan_next_page(self, callback = _dummy_callback):
        os.makedirs(self.docpath)
        page = self.get_nb_pages() + 1 # remember: we start counting from 1
        callback(self.SCAN_STEP_SCAN, 0, 100)
        self._scan(callback, page)
        callback(self.SCAN_STEP_OCR, 0, 100)
        self._ocr(callback, page)

