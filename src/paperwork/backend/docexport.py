import os

from .common.doc import dummy_export_progress_cb


class MultipleDocExporter(object):
    can_select_format = False
    can_change_quality = False

    def __init__(self, doclist):
        self.doclist = doclist
        self.exporters = [doc.build_exporter() for doc in doclist]
        self.ref_exporter = self.exporters[0]
        self.ref_doc = doclist[0]

        self.nb_pages = 0
        for doc in self.doclist:
            self.nb_pages += doc.nb_pages

        for idx in range(0, len(self.exporters)):
            exporter = self.exporters[idx]
            doc = self.doclist[idx]

            if exporter.can_select_format:
                self.can_select_format = True
            if (exporter.can_select_format and
                    not self.ref_exporter.can_select_format):
                self.ref_exporter = exporter
                self.ref_doc = doc
            if exporter.can_change_quality:
                self.can_change_quality = True
            if (exporter.can_change_quality and
                    not self.ref_exporter.can_change_quality):
                self.ref_exporter = exporter
                self.ref_doc = doc

    def get_mime_type(self):
        return None  # folder

    def get_file_extensions(self):
        return None  # folder

    def set_quality(self, quality):
        for exporter in self.exporters:
            if exporter.can_change_quality:
                exporter.set_quality(quality)

    def set_page_format(self, page_format):
        for exporter in self.exporters:
            if exporter.can_select_format:
                exporter.set_page_format(page_format)

    def set_postprocess_func(self, func):
        for exporter in self.exporters:
            if exporter.can_change_quality:
                exporter.set_postprocess_func(func)

    def refresh(self):
        return self.ref_exporter.refresh()

    def estimate_size(self):
        size = self.ref_exporter.estimate_size()
        size *= self.nb_pages
        size /= self.ref_doc.nb_pages
        return size

    def get_img(self):
        return self.ref_exporter.get_img()

    def save(self, target_path, progress_cb=dummy_export_progress_cb):
        progress_cb(0, len(self.exporters))
        for (idx, exporter) in enumerate(self.exporters):
            progress_cb(idx, len(self.exporters))
            doc = exporter.doc
            filename = "{}.pdf".format(doc.docid)
            filepath = os.path.join(target_path, filename)
            exporter.save(filepath, dummy_export_progress_cb)
        progress_cb(len(self.exporters), len(self.exporters))
        return target_path
