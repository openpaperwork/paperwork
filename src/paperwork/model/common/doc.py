import codecs
import datetime
import os
import os.path
import time

from paperwork.model.common.page import BasicPage
from paperwork.model.labels import Label
from paperwork.util import dummy_progress_cb


class BasicDoc(object):
    LABEL_FILE = "labels"
    DOCNAME_FORMAT = "%Y%m%d_%H%M_%S"

    nb_pages = 0
    pages = []
    can_edit = False

    def __init__(self, docpath, docid=None):
        if docid == None:
            self.docid = time.strftime(self.DOCNAME_FORMAT)
            self.path = os.path.join(docpath, self.docid)
        else:
            self.docid = docid
            self.path = docpath

    def __str__(self):
        return self.docid

    def redo_ocr(self, ocrlang, callback=dummy_progress_cb):
        """
        Run the OCR again on all the pages of the document

        Arguments
        """
        nb_pages = self.nb_pages
        for i in range(0, nb_pages):
            callback(i, nb_pages, BasicPage.SCAN_STEP_OCR, self)
            page = self.pages[i]
            page.redo_ocr(ocrlang)

    def print_page_cb(self, print_op, print_context, page_nb):
        raise NotImplementedError()

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
        print "Destroying doc: %s" % self.path
        for root, dirs, files in os.walk(self.path, topdown=False):
            for filename in files:
                filepath = os.path.join(root, filename)
                print "Deleting file %s" % filepath
                os.unlink(filepath)
            for dirname in dirs:
                dirpath = os.path.join(root, dirname)
                print "Deleting dir %s" % dirpath
                os.rmdir(dirpath)
        os.rmdir(self.path)
        print "Done"

    def add_label(self, label):
        """
        Add a label on the document.
        """
        if label in self.labels:
            return
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'a',
                        encoding='utf-8') as file_desc:
            file_desc.write("%s,%s\n" % (label.name, label.get_color_str()))

    def remove_label(self, to_remove):
        """
        Remove a label from the document. (-> rewrite the label file)
        """
        if not to_remove in self.labels:
            return
        labels = self.labels
        labels.remove(to_remove)
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'w',
                        encoding='utf-8') as file_desc:
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
            with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'r',
                             encoding='utf-8') as file_desc:
                for line in file_desc.readlines():
                    line = line.strip()
                    (label_name, label_color) = line.split(",")
                    labels.append(Label(name=label_name, color=label_color))
        except IOError:
            pass
        return labels

    labels = property(__get_labels)

    def update_label(self, old_label, new_label):
        """
        Update a label

        Will go on each document, and replace 'old_label' by 'new_label'
        """
        print ("%s : Updating label ([%s] -> [%s])"
               % (str(self), str(old_label), str(new_label)))
        labels = self.labels
        try:
            labels.remove(old_label)
        except ValueError:
            # this document doesn't have this label
            return
        labels.append(new_label)
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'w',
                        encoding='utf-8') as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))

    @staticmethod
    def get_export_formats():
        raise NotImplementedError()

    def build_exporter(self, file_format='pdf'):
        """
        Returns:
            Returned object must implement the following methods:
            .can_set_quality()
            .set_quality(quality_pourcent)
            .estimate_size() : returns the size in bytes
            .get_img() : returns a PIL Image
            .get_mime_type()
            .save(file_path)
        """
        raise NotImplementedError()

    def __doc_cmp(self, other):
        """
        Comparison function. Can be used to sort docs alphabetically.
        """
        if other == None:
            return -1
        return cmp(self.docid, other.docid)

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
        return hash(self.docid)

    def __get_name(self):
        """
        Returns the localized name of the document (see l10n)
        """
        try:
            split = self.docid.split("_")
            short_docid = "_".join(split[:3])
            extra = " ".join(split[3:])
            datetime_obj = datetime.datetime.strptime(
                    short_docid, self.DOCNAME_FORMAT)
            final = datetime_obj.strftime("%x %X")
            if extra != "":
                final += (" (%s)" % (extra))
            return final
        except Exception, exc:
            print ("Unable to parse document id [%s]: %s"
                   % (self.docid, str(exc)))
            return self.docid

    name = property(__get_name)

