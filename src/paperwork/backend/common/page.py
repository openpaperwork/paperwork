#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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

from copy import copy
import PIL.Image
import os.path

import numpy
from scipy import sparse
from scipy.sparse.csr import csr_matrix
from skimage import feature
from sklearn.preprocessing import normalize

from paperwork.backend.util import split_words


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

    # The width of the thumbnails is defined arbitrarily
    DEFAULT_THUMB_WIDTH = 150
    # The height of the thumbnails is defined based on the A4 format
    # proportions
    DEFAULT_THUMB_HEIGHT = 212

    EXT_THUMB = "thumb.jpg"
    FILE_PREFIX = "paper."

    boxes = []
    img = None
    size = (0, 0)

    can_edit = False

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

    def _get_filepath(self, ext):
        """
        Returns a file path relative to this page
        """
        filename = ("%s%d.%s" % (self.FILE_PREFIX, self.page_nb + 1, ext))
        return os.path.join(self.doc.path, filename)

    def __make_thumbnail(self, width, height):
        """
        Create the page's thumbnail
        """
        img = self.img
        (w, h) = img.size
        factor = max(
            (float(w) / width),
            (float(h) / height)
        )
        w /= factor
        h /= factor
        img = img.resize((int(w), int(h)), PIL.Image.ANTIALIAS)
        return img

    def _get_thumb_path(self):
        return self._get_filepath(self.EXT_THUMB)

    def get_thumbnail(self, width, height):
        """
        thumbnail with a memory cache
        """
        if ((width, height) == self.__thumbnail_cache[1]):
            return self.__thumbnail_cache[0]

        # get from the file
        try:
            if (os.path.getmtime(self.get_doc_file_path()) <
                    os.path.getmtime(self._get_thumb_path())):
                thumbnail = PIL.Image.open(self._get_thumb_path())
            else:
                thumbnail = self.__make_thumbnail(width, height)
                thumbnail.save(self._get_thumb_path())
        except:
            thumbnail = self.__make_thumbnail(width, height)
            thumbnail.save(self._get_thumb_path())

        self.__thumbnail_cache = (thumbnail, (width, height))
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

    def print_page_cb(self, print_op, print_context, keep_refs={}):
        raise NotImplementedError()

    def destroy(self):
        raise NotImplementedError()

    def get_export_formats(self):
        return self.__prototype_exporters.keys()

    def build_exporter(self, file_format='PNG'):
        return copy(self.__prototype_exporters[file_format.upper()])

    def __str__(self):
        return "%s p%d" % (str(self.doc), self.page_nb + 1)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if other is None:
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

    def extract_features(self):
        """
        compute image data to present features for the estimators
        """
        image = self.get_thumbnail(BasicPage.DEFAULT_THUMB_WIDTH,
                                   BasicPage.DEFAULT_THUMB_HEIGHT)
        image = image.convert('RGB')

        # use the first two channels of color histogram
        histogram = image.histogram()
        separated_histo = []
        separated_histo.append(histogram[0:256])
        separated_histo.append(histogram[256:256*2])
        # use the grayscale histogram with a weight of 2
        separated_histo.append([i*2 for i in image.convert('L').histogram()])
        separated_flat_histo = []
        for histo in separated_histo:
            # flatten histograms
            window_len = 4
            s = numpy.r_[
                histo[window_len-1:0:-1],
                histo,
                histo[-1:-window_len:-1]
            ]
            w = numpy.ones(window_len, 'd')
            separated_flat_histo.append(csr_matrix(
                numpy.convolve(w/w.sum(), s, mode='valid'))
                .astype(numpy.float64))
        flat_histo = normalize(sparse.hstack(separated_flat_histo), norm='l1')

        # hog feature extraction
        # must resize to multiple of 8 because of skimage hog bug
        hog_features = feature.hog(numpy.array(image.resize((144, 144))
                                               .convert('L')),
                                   normalise=False)
        hog_features = csr_matrix(hog_features).astype(numpy.float64)
        hog_features = normalize(hog_features, norm='l1')

        # concatenate
        features = sparse.hstack([flat_histo, hog_features * 3])

        return features


class DummyPage(object):
    page_nb = -1
    text = ""
    boxes = []
    keywords = []
    img = None

    def __init__(self, parent_doc):
        self.doc = parent_doc

    def _get_filepath(self, ext):
        raise NotImplementedError()

    def get_thumbnail(self, width):
        raise NotImplementedError()

    def print_page_cb(self, print_op, print_context):
        raise NotImplementedError()

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
