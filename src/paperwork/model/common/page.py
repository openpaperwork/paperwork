import codecs
import Image
import os
import os.path
import re

from paperwork.util import split_words


class BasicPage(object):
    SCAN_STEP_SCAN = "scanning"
    SCAN_STEP_OCR = "ocr"

    text = ""
    boxes = []
    img = None

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

    def get_boxes(self, sentence):
        """
        Get all the boxes corresponding the given sentence

        Arguments:
            sentence --- can be string (will be splited), or an array of strings
        Returns:
            an array of boxes (see pyocr boxes)
        """
        if isinstance(sentence, unicode):
            keywords = split_words(sentence)
        else:
            assert(isinstance(sentence, list))
            keywords = sentence

        output = []
        for keyword in keywords:
            for box in self.boxes:
                # unfold generator output
                words = []
                for word in split_words(box.content):
                    words.append(word)
                if keyword in words:
                    output.append(box)
        return output

    @staticmethod
    def get_export_formats():
        raise NotImplementedError()

    def build_exporter(self, file_format='png'):
        """
        Returns:
            Same thing than paperwork.model.common.doc.BasicDoc.build_exporter()
        """
        raise NotImplementedError()


    def __str__(self):
        return "%s p%d" % (str(self.doc), self.page_nb + 1)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if None == other:
            return False
        return self.doc == other.doc and self.page_nb == other.page_nb

    def __get_keywords(self):
        """
        Get all the keywords related of this page

        Returns:
            An array of strings
        """
        for line in self.text:
            for word in split_words(line):
                yield(word)

    keywords = property(__get_keywords)

