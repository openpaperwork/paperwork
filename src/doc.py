import os
import os.path
import time

from page import ScannedPage
from tags import Tag
from util import dummy_progress_callback

class ScannedDoc(object):
    TAG_FILE = "labels"

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

    def get_path(self):
        return self.docpath

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

    def scan_next_page(self, device, ocrlang, callback = dummy_progress_callback):
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

    def redo_ocr(self, ocrlang):
        nb_pages = self.get_nb_pages()
        for i in range(0, nb_pages):
            page = ScannedPage(self, i+1)
            page.redo_ocr(ocrlang)

    def add_tag(self, tag):
        if tag in self.get_tags():
            return
        with open(os.path.join(self.docpath, self.TAG_FILE), 'a') as fd:
            fd.write("%s,%s\n" % (tag.name, tag.get_color_str()))

    def remove_tag(self, to_remove):
        tags = self.get_tags()
        tags.remove(to_remove)
        with open(os.path.join(self.docpath, self.TAG_FILE), 'w') as fd:
            for tag in tags:
                fd.write("%s,%s\n" % (tag.name, tag.get_color_str()))

    def get_tags(self):
        tags = []
        try:
            with open(os.path.join(self.docpath, self.TAG_FILE), 'r') as fd:
                for line in fd.readlines():
                    line = line.strip()
                    (tag_name, tag_color) = line.split(",")
                    tags.append(Tag(name = tag_name, color = tag_color))
        except IOError, e:
            print "Error while reading tags from '%s': %s" % (self.docpath, str(e))
        return tags

