import codecs
import Image
import os
import os.path
import re

class BasicPage(object):
    text = ""
    boxes = []
    img = None
    keywords = []

    def __init__(self, doc, page_nb):
        """
        Don't create directly. Please use ImgDoc.get_page()
        """
        self.doc = doc
        self.page_nb = page_nb
        assert(self.page_nb >= 0)

    def get_thumbnail(self, width):
        raise NotImplementedError()

    def print_page_cb(self, print_op, print_context):
        raise NotImplementedError()

    def redo_ocr(self, ocrlang):
        raise NotImplementedError()

    def destroy(self):
        raise NotImplementedError()

    def __str__(self):
        return "%s p%d" % (str(self.doc), self.page_nb + 1)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if None == other:
            return False
        return self.doc == other.doc and self.page_nb == other.page_nb
