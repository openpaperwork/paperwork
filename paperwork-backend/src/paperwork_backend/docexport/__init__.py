"""
Doc and page exporting are designed as pipelines.
UI build the pipelines and run it.

Data to export are represented as tree:
    Document set to export: data = set of (doc_id, doc_url))
    |-- Document to export: data = (doc_id, doc_url)
    |   |-- Page to export: data = (page_idx)
    |   |   |-- img_boxes: data = (Pillow image, boxes)
    |   |-- Page to export
    |
    |-- Document_to_export
    | (...)

When a pipes says it needs a given type in input, it means the content
of the tree must be extended up to this data type.

For example, if a pipe says it needs ExportDataType.PAGE as input, it must
get an ExportData of type ExportDataType.DOCUMENT_SET as input, but expanded
up to ExportDataType.PAGE:
    Document set to export
    |-- Document to export
    |   |-- Page to export
    |   |-- Page to export
    |
    |-- Document_to_export
    | (...)

It must *not* be expanded any further either (for instance, no img+boxes
(ExportDataType.IMG_BOXES) if the pipe says it expects a ExportDataType.PAGE
as input).

There are pipes dedicated to expanding unexpanded data (see docexport.generic).
"""
import abc
import enum

import openpaperwork_core


class ExportDataType(enum.Enum):
    DOCUMENT_SET = 0
    DOCUMENT = 1
    PAGE = 2
    IMG_BOXES = 3

    # the following ones are for final output only.
    # A list of paths (str) will be returned instead of an ExportData object.
    OUTPUT_URL_FILE = -1


class ExportData:
    def __init__(self, dtype, data):
        self.dtype = dtype
        self.data = data
        self._children = []
        self.expanded = False

    def clone(self):
        out = ExportData(self.dtype, self.data)
        out._children = [c.clone() for c in self._children]
        out.expanded = self.expanded
        return out

    def iter(self, dtype):
        if self.dtype == dtype:
            yield self
            return
        for c in self.get_children():
            for s in c.iter(dtype):
                yield (self, s)

    def get_children(self):
        assert self.expanded
        return self._children

    def set_children(self, children):
        self._children = children
        self.expanded = True

    @staticmethod
    def build_doc_set(docs):
        return ExportData(ExportDataType.DOCUMENT_SET, docs)

    @staticmethod
    def build_doc(doc_id, doc_url):
        root = ExportData.build_doc_set({(doc_id, doc_url)})
        doc = ExportData(ExportDataType.DOCUMENT, (doc_id, doc_url))
        root.set_children([doc])
        return root

    @staticmethod
    def build_page(doc_id, doc_url, page_idx):
        return ExportData.build_pages(doc_id, doc_url, [page_idx])

    @staticmethod
    def build_pages(doc_id, doc_url, page_indexes):
        root = ExportData.build_doc_set({(doc_id, doc_url)})
        doc = ExportData(ExportDataType.DOCUMENT, (doc_id, doc_url))
        pages = [
            ExportData(ExportDataType.PAGE, page_idx)
            for page_idx in page_indexes
        ]
        doc.set_children(pages)
        root.set_children([doc])
        return root


class AbstractExportPipe(abc.ABC):
    """
    Pipes are used by the frontend/user to build an export pipeline (a list of
    pipes to apply in a specific order).

    There are input pipes, taking either DOCUMENT_SET, DOCUMENT, or PAGES
    as input.
    There are output pipes, providing a file URL (FILE_URL) as output
    or a directory URL.
    And there are processing pipes (usually taking Pillow images and text boxes
    as input (IMG_BOXES)).

    Once the pipeline is defined, the frontend code can obtain promises
    from the pipes (`export_get_pipe_*()`), chain them together, and schedule
    them (see get_promise()).
    """

    def __init__(self, name, input_type, output_type):
        """
        Arguments:
          name -- name of the export pipe
          input_type -- accepted ExportDataType
          output_type -- ExportDataType
        """
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
        self.can_change_quality = False
        self.can_change_page_format = False

        self.quality = 0.75
        self.page_format = (595.2755905511812, 841.8897637795276)  # A4

    def can_export_doc(self, doc_url):
        return False

    def can_export_page(self, doc_url, page_idx):
        return False

    @abc.abstractmethod
    def export(self, input_data, result="final", target_file_url=None):
        ...

    def get_promise(self, result='final', target_file_url=None):
        """
        Returns a promise.
        Beware that the promise will modify the ExportData object given as
        input. If you want to preserve your copy, please use
        ExportData.clone().

        Arguments:
        - result: either 'preview' (only one page) or 'final' (all pages)
        - target_file_url: Where the final pipe should write the file
          (None = temporary file)

        Returns:
        - A promise, that expect ExportData object as input and will
          return either an ExportData (if it must be chained to another pipe)
          or a list of str (list of paths)
        """
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.export, kwargs={
                "result": result,
                "target_file_url": target_file_url,
            }
        )

    def get_estimated_size_factor(self, input_data):
        """
        Return the factor to apply to the preview size to get an estimation
        of the final result size.

        Arguments:
          input_data -- ExportData. Won't be modified
        """
        return 1

    def set_quality(self, quality):
        """
        Allow to define an output quality (between 0 and 100).
        Check `can_change_quality` before calling this method.
        """
        assert self.can_change_quality
        self.quality = quality

    def set_page_format(self, page_format):
        """
        Allow to define the expected output page format.
        Check `can_change_quality` before calling this method.

        Arguments:
         page_format: tuple (width, height), in points (1 point == 1/72.0 inch)
        """
        assert self.can_change_page_format
        self.page_format = page_format

    def get_output_mime(self):
        """
        If the pipe outputs a file, specifies its mime type and
        a list of possible file extensions.
        None if it doesn't outputs a file.
        """
        return None

    @abc.abstractmethod
    def __str__(self):
        ...


class ExportDataTransformedImgBoxes(ExportData):
    """
    Page images takes a lot of memory --> we only generate them when actually
    requested.
    """
    def __init__(self, pipe, original_page):
        super().__init__(ExportDataType.PAGE, original_page.data)
        self.expanded = True
        self.pipe = pipe
        self.original_page = original_page

    def get_children(self):
        children = self.original_page.get_children()
        for img_boxes in children:
            (img, boxes) = img_boxes.data
            img = self.pipe.transform(img)
            yield ExportData(ExportDataType.IMG_BOXES, (img, boxes))


class AbstractSimpleTransformExportPipe(AbstractExportPipe):
    """
    Base template class for page image to page image transformations.
    """
    def __init__(self, core, name):
        super().__init__(
            name=name,
            input_type=ExportDataType.IMG_BOXES,
            output_type=ExportDataType.IMG_BOXES
        )
        self.core = core

    def transform(self, img):
        # sub-classes must implement it
        assert False

    def export(self, input_data, result='final', target_file_url=None):
        assert input_data.dtype == ExportDataType.DOCUMENT_SET

        docs = input_data.iter(ExportDataType.DOCUMENT)
        docs = list(docs)

        # replace the document page list by objects that will
        # generate their children (img+boxes) on-the-fly.
        for (doc_set, doc) in docs:
            assert doc.expanded
            doc.set_children([
                ExportDataTransformedImgBoxes(self, page)
                for page in doc.get_children()
            ])

        return input_data


class AbstractExportPipePlugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.pipes = []

    def get_interfaces(self):
        return ['export_pipes']

    def get_deps(self):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def export_get_pipe_by_name(self, name):
        for pipe in self.pipes:
            if pipe.name == name:
                return pipe

    def export_get_pipes_by_input(self, out: list, input_type):
        for pipe in self.pipes:
            if input_type == pipe.input_type:
                out.append(pipe)

    def export_get_pipes_by_doc_urls(self, out: list, doc_urls):
        for pipe in self.pipes:
            if pipe.input_type != ExportDataType.DOCUMENT:
                continue
            for doc_url in doc_urls:
                if not pipe.can_export_doc(doc_url):
                    break
            else:
                out.append(pipe)

    def export_get_pipes_by_doc_url(self, out: list, doc_url):
        return self.export_get_pipes_by_doc_urls(out, [doc_url])

    def export_get_pipes_by_page(self, out: list, doc_url, page_nb):
        for pipe in self.pipes:
            if pipe.input_type != ExportDataType.PAGE:
                continue
            if not pipe.can_export_page(doc_url, page_nb):
                continue
            out.append(pipe)
