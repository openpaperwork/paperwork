import os
import os.path
import time

from page import ScannedPage

class ScannedDoc(object):
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
                if f[-4:].lower() != "."+ScannedPage.EXT_IMG:
                    continue
                i += 1
            return i
        except Exception, e:
            print "Exception while trying to get the number of pages of '%s': %s" % (self.docid, e)
            return 0

    def _dummy_callback(step, progression, total):
        pass

    def scan_next_page(self, device, ocrlang, callback = _dummy_callback):
        try:
            os.makedirs(self.docpath)
        except OSError:
            pass

        page_nb = self.get_nb_pages() + 1 # remember: we start counting from 1
        page = ScannedPage(self, page_nb)
        page.scan_page(device, ocrlang, callback)

    def get_page(self, page):
        return ScannedPage(self, page)

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

    def print_page(self, print_op, print_context, page_nb):
        """
        Called for printing operation by Gtk

        Arguments:
            page --- Starts counting from 0 !
        """
        page = ScannedPage(self, page_nb+1)
        page.print_page(print_op, print_context)

