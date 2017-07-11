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

import datetime
import gettext
import logging
import time
import hashlib

from ..labels import Label


_ = gettext.gettext
logger = logging.getLogger(__name__)


class BasicDoc(object):
    LABEL_FILE = "labels"
    DOCNAME_FORMAT = "%Y%m%d_%H%M_%S"
    EXTRA_TEXT_FILE = "extra.txt"

    pages = []
    can_edit = False

    def __init__(self, fs, docpath, docid=None):
        """
        Basic init of common parts of doc.

        Note regarding subclassing: *do not* load the document
        content in __init__(). It would reduce in a huge performance loose
        and thread-safety issues. Load the content on-the-fly when requested.
        """
        self.fs = fs
        docpath = fs.safe(docpath)
        if docid is None:
            # new empty doc
            # we must make sure we use an unused id
            basic_docid = time.strftime(self.DOCNAME_FORMAT)
            extra = 0
            docid = basic_docid
            path = self.fs.join(docpath, docid)
            while self.fs.exists(path):
                extra += 1
                docid = "%s_%d" % (basic_docid, extra)
                path = self.fs.join(docpath, docid)

            self.__docid = docid
            self.path = path
        else:
            self.__docid = docid
            self.path = docpath

        # We need to keep track of the labels:
        # When updating bayesian filters for label guessing,
        # we need to know the new label list, but also the *previous* label
        # list
        self._previous_labels = self.labels[:]

    def __str__(self):
        return self.__docid

    def __get_id(self):
        return self.__docid

    id = property(__get_id)

    def __get_last_mod(self):
        raise NotImplementedError()

    last_mod = property(__get_last_mod)

    def __get_nb_pages(self):
        return self._get_nb_pages()

    nb_pages = property(__get_nb_pages)

    def print_page_cb(self, print_op, print_context, page_nb, keep_refs={}):
        """
        Arguments:
            keep_refs --- Workaround ugly as fuck to keep some object alive
                          (--> non-garbage-collected) during the whole
                          printing process
        """
        raise NotImplementedError()

    def __get_doctype(self):
        raise NotImplementedError()

    def get_docfilehash(self):
        raise NotImplementedError()

    doctype = property(__get_doctype)

    def __get_keywords(self):
        """
        Yield all the keywords contained in the document.
        """
        for page in self.pages:
            for keyword in page.keywords:
                yield(keyword)

    keywords = property(__get_keywords)

    def destroy(self):
        """
        Delete the document. The *whole* document. There will be no survivors.
        """
        logger.info("Destroying doc: %s" % self.path)
        self.fs.rm_rf(self.path)
        logger.info("Done")

    def add_label(self, label):
        """
        Add a label on the document.
        """
        if label in self.labels:
            return
        with self.fs.open(self.fs.join(self.path, self.LABEL_FILE), 'a') \
                as file_desc:
            file_desc.write("%s,%s\n" % (label.name, label.get_color_str()))

    def remove_label(self, to_remove):
        """
        Remove a label from the document. (-> rewrite the label file)
        """
        if to_remove not in self.labels:
            return
        labels = self.labels
        labels.remove(to_remove)
        with self.fs.open(self.fs.join(self.path, self.LABEL_FILE), 'w') \
                as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))

    def __get_labels(self):
        """
        Read the label file of the documents and extract all the labels

        Returns:
            An array of labels.Label objects
        """
        labels = []
        try:
            with self.fs.open(self.fs.join(self.path, self.LABEL_FILE),
                                'r') as file_desc:
                for line in file_desc.readlines():
                    line = line.strip()
                    (label_name, label_color) = line.split(",", 1)
                    labels.append(Label(name=label_name,
                                        color=label_color))
        except IOError:
            pass
        return labels

    def __set_labels(self, labels):
        """
        Add a label on the document.
        """
        with self.fs.open(self.fs.join(self.path, self.LABEL_FILE), 'w') \
                as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))

    labels = property(__get_labels, __set_labels)

    def get_index_text(self):
        txt = u""
        for page in self.pages:
            txt += u"\n".join([str(line) for line in page.text])
        extra_txt = self.extra_text
        if extra_txt != u"":
            txt += u"\n" + extra_txt + u"\n"
        txt = txt.strip()
        if txt == u"":
            # make sure the text field is not empty. Whoosh doesn't like that
            txt = u"empty"
        return txt

    def _get_text(self):
        txt = u""
        for page in self.pages:
            txt += u"\n".join([str(line) for line in page.text])
        extra_txt = self.extra_text
        if extra_txt != u"":
            txt += u"\n" + extra_txt + u"\n"
        txt = txt.strip()
        return txt

    text = property(_get_text)

    def get_index_labels(self):
        return u",".join([str(label.name)
                          for label in self.labels])

    def update_label(self, old_label, new_label):
        """
        Update a label

        Replace 'old_label' by 'new_label'
        """
        logger.info("%s : Updating label ([%s] -> [%s])"
                    % (str(self), old_label.name, new_label.name))
        labels = self.labels
        try:
            labels.remove(old_label)
        except ValueError:
            # this document doesn't have this label
            return

        logger.info("%s : Updating label ([%s] -> [%s])"
                    % (str(self), old_label.name, new_label.name))
        labels.append(new_label)
        with self.fs.open(self.fs.join(self.path, self.LABEL_FILE), 'w') \
                as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))

    @staticmethod
    def get_export_formats():
        raise NotImplementedError()

    def build_exporter(self, file_format='pdf', preview_page_nb=0):
        """
        Returns:
            Returned object must implement the following methods/attributes:
            .obj
            .export_format
            .can_change_quality = (True|False)
            .set_quality(quality_pourcent)  # if can_change_quality
            .set_postprocess_func(func)  # if can_change_quality
            .estimate_size() : returns the size in bytes
            .get_img() : returns a Pillow Image
            .get_mime_type()
            .get_file_extensions()
            .save(file_path, progress_cb=dummy_export_progress_cb)
            progress_cb(current, total)
        """
        raise NotImplementedError()

    def __doc_cmp(self, other):
        """
        Comparison function. Can be used to sort docs alphabetically.
        """
        if other is None:
            return -1
        if self.is_new and other.is_new:
            return 0
        if self.__docid < other.__docid:
            return -1
        elif self.__docid == other.__docid:
            return 0
        else:
            return 1

    def __lt__(self, other):
        return self.__doc_cmp(other) < 0

    def __gt__(self, other):
        return self.__doc_cmp(other) > 0

    def __eq__(self, other):
        return self.__doc_cmp(other) == 0

    def __le__(self, other):
        return self.__doc_cmp(other) <= 0

    def __ge__(self, other):
        return self.__doc_cmp(other) >= 0

    def __ne__(self, other):
        return self.__doc_cmp(other) != 0

    def __hash__(self):
        return hash(self.__docid)

    def __is_new(self):
        return not self.fs.exists(self.path)

    is_new = property(__is_new)

    @staticmethod
    def get_name(date):
        return date.strftime("%x")

    @staticmethod
    def parse_name(date_str):
        return datetime.datetime.strptime(date_str, "%x")

    def __get_name(self):
        """
        Returns the localized name of the document (see l10n)
        """
        if self.is_new:
            return _("New document")
        try:
            split = self.__docid.split("_")
            short_docid = "_".join(split[:3])
            datetime_obj = datetime.datetime.strptime(
                short_docid, self.DOCNAME_FORMAT)
            final = datetime_obj.strftime("%x")
            return final
        except Exception as exc:
            logger.error("Unable to parse document id [%s]: %s"
                         % (self.docid, exc))
            return self.docid

    name = property(__get_name)

    def __get_docid(self):
        return self.__docid

    def _set_docid(self, new_base_docid):
        workdir = self.fs.dirname(self.path)
        new_docid = new_base_docid
        new_docpath = self.fs.join(workdir, new_docid)
        idx = 0

        while self.fs.exists(new_docpath):
            idx += 1
            new_docid = new_base_docid + ("_%02d" % idx)
            new_docpath = self.fs.join(workdir, new_docid)

        self.__docid = new_docid
        if self.path != new_docpath:
            logger.info("Changing docid: %s -> %s", self.path, new_docpath)
            self.fs.rename(self.path, new_docpath)
            self.path = new_docpath

    docid = property(__get_docid, _set_docid)

    def __get_date(self):
        try:
            split = self.__docid.split("_")[0]
            return (datetime.datetime(
                int(split[0:4]),
                int(split[4:6]),
                int(split[6:8])))
        except (IndexError, ValueError):
            return (datetime.datetime(1900, 1, 1))

    def __set_date(self, new_date):
        new_id = ("%02d%02d%02d_0000_01"
                  % (new_date.year,
                     new_date.month,
                     new_date.day))
        self.docid = new_id

    date = property(__get_date, __set_date)

    def __get_extra_text(self):
        extra_txt_file = self.fs.join(self.path, self.EXTRA_TEXT_FILE)
        if not self.fs.exists(extra_txt_file):
            return u""
        with self.fs.open(extra_txt_file, 'r') as file_desc:
            text = file_desc.read()
            return text

    def __set_extra_text(self, txt):
        extra_txt_file = self.fs.join(self.path, self.EXTRA_TEXT_FILE)

        txt = txt.strip()
        if txt == u"":
            self.fs.unlink(extra_txt_file)
        else:
            with self.fs.open(extra_txt_file, 'w') as file_desc:
                file_desc.write(txt)

    extra_text = property(__get_extra_text, __set_extra_text)

    @staticmethod
    def hash_file(fs, path):
        with fs.open(path, 'rb') as fd:
            content = fd.read()
            dochash = hashlib.sha256(content).hexdigest()
        return int(dochash, 16)

    def clone(self):
        raise NotImplementedError()

    def has_ocr(self):
        """
        Indicates if the OCR has been ran on this document.
        """
        if self.nb_pages <= 0:
            return False
        return self.pages[0].has_ocr()
