#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
#    Copyright (C) 2012  Sebastien Maccagnoni-Munch
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
"""
Code for managing documents (not page individually ! see page.py for that)
"""

import errno
import logging

from ..common.doc import BasicDoc
from ..img.page import ImgPage

logger = logging.getLogger(__name__)


class _ImgPagesIterator(object):

    """
    Iterates on a page list
    """

    def __init__(self, page_list):
        self.idx = 0
        self.page_list = page_list

    def __iter__(self):
        return self

    def next(self):
        """
        Provide the next element of the list.
        """
        if self.idx >= len(self.page_list):
            raise StopIteration()
        page = self.page_list[self.idx]
        self.idx += 1
        return page

    def __next__(self):
        return self.next()


class _ImgPages(object):

    """
    Page list. Page are accessed using [] operator.
    """

    def __init__(self, doc):
        self.doc = doc
        self.__pages = None

    def add(self, page):
        self.__pages.append(page)

    def __getitem__(self, idx):
        if not self.__pages:
            nb_pages = self.doc.nb_pages
            self.__pages = [
                ImgPage(self.doc, i) for i in range(0, nb_pages)
            ]
        return self.__pages[idx]

    def __len__(self):
        return self.doc.nb_pages

    def __contains__(self, page):
        return (page.doc == self.doc and page.page_nb <= self.doc.nb_pages)

    def __eq__(self, other):
        return (self.doc == other.doc)

    def __iter__(self):
        return _ImgPagesIterator(self)


class ImgDoc(BasicDoc):

    """
    Represents a document (aka a set of pages + labels).
    """
    IMPORT_IMG_EXTENSIONS = [
        ".jpg",
        ".jpeg",
        ".png"
    ]
    can_edit = True
    doctype = u"Img"

    def __init__(self, fs, docpath, docid=None):
        """
        Arguments:
            docpath --- For an existing document, the path to its folder. For
                a new one, the rootdir of all documents
            docid --- Document Id (ie folder name). Use None for a new document
        """
        BasicDoc.__init__(self, fs, docpath, docid)

    def clone(self):
        return ImgDoc(self.fs, self.path, self.docid)

    def __get_last_mod(self):
        last_mod = 0.0
        for page in self.pages:
            if last_mod < page.last_mod:
                last_mod = page.last_mod
        labels_path = self.fs.join(self.path, BasicDoc.LABEL_FILE)
        try:
            file_last_mod = self.fs.getmtime(labels_path)
            if file_last_mod > last_mod:
                last_mod = file_last_mod
        except OSError:
            pass
        extra_txt_path = self.fs.join(self.path, BasicDoc.EXTRA_TEXT_FILE)
        try:
            file_last_mod = self.fs.getmtime(extra_txt_path)
            if file_last_mod > last_mod:
                last_mod = file_last_mod
        except OSError:
            pass
        return last_mod

    last_mod = property(__get_last_mod)

    @property
    def pages(self):
        return _ImgPages(self)

    def _get_nb_pages(self):
        """
        Compute the number of pages in the document. It basically counts
        how many JPG files there are in the document.
        """
        try:
            filelist = self.fs.listdir(self.path)
            count = 0
            for filepath in filelist:
                filename = self.fs.basename(filepath)
                if not ImgPage.FILE_REGEX.match(filename):
                    continue
                count += 1
            return count
        except IOError as exc:
            logger.debug("Exception while trying to get the number of"
                         " pages of '%s': %s", self.docid, exc)
            return 0
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                logger.error("Exception while trying to get the number of"
                             " pages of '%s': %s", self.docid, exc)
                raise
            return 0

    def print_page_cb(self, print_op, print_context, page_nb, keep_refs={}):
        """
        Called for printing operation by Gtk
        """
        page = ImgPage(self, page_nb)
        page.print_page_cb(print_op, print_context, keep_refs=keep_refs)

    def steal_page(self, page):
        """
        Steal a page from another document
        """
        if page.doc == self:
            return
        self.fs.mkdir_p(self.path)

        new_page = ImgPage(self, self.nb_pages)
        logger.info("%s --> %s" % (str(page), str(new_page)))
        new_page._steal_content(page)

    def get_docfilehash(self):
        if self._get_nb_pages() == 0:
            logger.warn("WARNING: Document %s is empty" % self.docid)
            dochash = 0
        else:
            dochash = 0
            for page in self.pages:
                dochash ^= page.get_docfilehash()
        return dochash

    def add_page(self, img, boxes):
        self.fs.mkdir_p(self.path)
        logger.info("Adding page %d to %s (%s)",
                    self.nb_pages, str(self), self.path)
        page = ImgPage(self, self.nb_pages)
        page.img = img
        page.boxes = boxes
        return self.pages[-1]

    def insert_page(self, img, boxes, page_nb):
        self.fs.mkdir_p(self.path)

        logger.info("Inserting page %d to %s" % (page_nb, str(self)))

        if page_nb > self.nb_pages:
            page_nb = self.nb_pages

        # make a hole ..
        pages = self.pages
        for page_nb in range(self.nb_pages - 1, page_nb - 1, -1):
            page = pages[page_nb]
            page.change_index(offset=1)

        # .. and fill it
        page = ImgPage(self, page_nb)
        page.img = img
        page.boxes = boxes
        return self.pages[page_nb]


def is_img_doc(fs, docpath):
    if not fs.isdir(docpath):
        return False
    try:
        filelist = fs.listdir(docpath)
    except OSError as exc:
        logger.warn("Warning: Failed to list files in %s: %s"
                    % (docpath, str(exc)))
        return False
    for filepath in filelist:
        if (filepath.lower().endswith(ImgPage.EXT_IMG) and
                not filepath.lower().endswith(ImgPage.EXT_THUMB)):
            return True
    return False
