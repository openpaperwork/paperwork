#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
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

import codecs
from copy import copy
import PIL.Image
import os
import os.path
import re

from paperwork.util import split_words


class PageExporter(object):
    can_select_format = False
    can_change_quality = True

    def __init__(self, page, img_format='PNG', mime='image/png',
                 valid_exts=['png']):
        self.page = page
        self.img_format = img_format
        self.mime = mime
        self.valid_exts = valid_exts
        self.__quality = 75
        self.__img = None

    def get_mime_type(self):
        return self.mime

    def get_file_extensions(self):
        return self.valid_exts

    def save(self, target_path):
        # the user gives us a quality between 0 and 100
        # but PIL expects a quality between 1 and 75
        quality = int(float(self.__quality) / 100.0 * 74.0) + 1
        # We also adjust the size of the image
        resize_factor = float(self.__quality) / 100.0

        img = self.page.img

        new_size = (int(resize_factor * img.size[0]),
                    int(resize_factor * img.size[1]))
        img = img.resize(new_size, PIL.Image.ANTIALIAS)

        img.save(target_path, self.img_format, quality=quality)
        return target_path

    def refresh(self):
        tmp = "%s.%s" % (os.tempnam(None, "paperwork_export_"),
                         self.valid_exts[0])
        path = self.save(tmp)
        img = PIL.Image.open(path)
        img.load()

        self.__img = (path, img)

    def set_quality(self, quality):
        self.__quality = int(quality)
        self.__img = None

    def estimate_size(self):
        if self.__img is None:
            self.refresh()
        return os.path.getsize(self.__img[0])

    def get_img(self):
        if self.__img is None:
            self.refresh()
        return self.__img[1]

    def __str__(self):
        return self.img_format

    def __copy__(self):
        return PageExporter(self.page, self.img_format, self.mime,
                            self.valid_exts)


class BasicPage(object):
    SCAN_STEP_SCAN = "scanning"
    SCAN_STEP_OCR = "ocr"

    boxes = []
    img = None

    def __init__(self, doc, page_nb):
        """
        Don't create directly. Please use ImgDoc.get_page()
        """
        self.doc = doc
        self.page_nb = page_nb

        self.__thumbnail_cache = (None, 0)
        self.__text_cache = None

        assert(self.page_nb >= 0)
        self.__prototype_exporters = {
            'PNG': PageExporter(self, 'PNG', 'image/png', ["png"]),
            'JPEG': PageExporter(self, 'JPEG', 'image/jpeg', ["jpeg", "jpg"]),
        }

    def __get_pageid(self):
        return self.doc.docid + "/" + str(self.page_nb)

    pageid = property(__get_pageid)

    def _get_thumbnail(self, width):
        raise NotImplementedError()

    def get_thumbnail(self, width):
        if (width == self.__thumbnail_cache[1]):
            return self.__thumbnail_cache[0]
        thumbnail = self._get_thumbnail(width)
        self.__thumbnail_cache = (thumbnail, width)
        return thumbnail

    def drop_cache(self):
        self.__thumbnail_cache = (None, 0)
        self.__text_cache = None

    def __get_text(self):
        if self.__text_cache is not None:
            return self.__text_cache
        self.__text_cache = self._get_text()
        return self.__text_cache

    text = property(__get_text)

    def print_page_cb(self, print_op, print_context):
        raise NotImplementedError()

    def redo_ocr(self, langs):
        raise NotImplementedError()

    def destroy(self):
        raise NotImplementedError()

    def get_boxes(self, sentence):
        """
        Get all the boxes corresponding the given sentence

        Arguments:
            sentence --- can be string (will be splited), or an array of
                strings
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
            for line in self.boxes:
                for box in line.word_boxes:
                    if keyword in box.content:
                        output.append(box)
                        continue
                    # unfold generator output
                    words = [x for x in split_words(box.content)]
                    if keyword in words:
                        output.append(box)
                        continue
        return output

    def get_export_formats(self):
        return self.__prototype_exporters.keys()

    def build_exporter(self, file_format='PNG'):
        return copy(self.__prototype_exporters[file_format.upper()])

    def __str__(self):
        return "%s p%d" % (str(self.doc), self.page_nb + 1)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if None == other:
            return False
        return self.doc == other.doc and self.page_nb == other.page_nb

    def __contains__(self, sentence):
        words = split_words(sentence)
        words = [word.lower() for word in words]
        txt = self.text
        for line in txt:
            line = line.lower()
            for word in words:
                if word in line:
                    return True
        return False

    def __get_keywords(self):
        """
        Get all the keywords related of this page

        Returns:
            An array of strings
        """
        txt = self.text
        for line in txt:
            for word in split_words(line):
                yield(word)

    keywords = property(__get_keywords)


class DummyPage(object):
    page_nb = -1
    text = ""
    boxes = []
    keywords = []
    img = None

    def __init__(self, parent_doc):
        self.doc = parent_doc

    def get_thumbnail(self, width):
        raise NotImplementedError()

    def print_page_cb(self, print_op, print_context):
        raise NotImplementedError()

    def redo_ocr(self, langs):
        pass

    def destroy(self):
        pass

    def get_boxes(self, sentence):
        return []

    def get_export_formats(self):
        return []

    def build_exporter(self, file_format='PNG'):
        raise NotImplementedError()

    def __str__(self):
        return "Dummy page"
