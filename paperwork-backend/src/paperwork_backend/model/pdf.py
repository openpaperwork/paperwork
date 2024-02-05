import datetime
import itertools
import logging
import math

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)

PDF_FILENAME = 'doc.pdf'
PASSWD_FILENAME = 'passwd.txt'
MAPPING_FILE = "page_map.csv"

PDF_RENDER_FACTOR = 4


def minmax_rects(rects):
    (mx1, my1, mx2, my2) = (math.inf, math.inf, 0, 0)
    for rectangle in rects:
        ((x1, y1), (x2, y2)) = (
            (int(rectangle.x1 * PDF_RENDER_FACTOR),
             int(rectangle.y2 * PDF_RENDER_FACTOR)),
            (int(rectangle.x2 * PDF_RENDER_FACTOR),
             int(rectangle.y1 * PDF_RENDER_FACTOR))
        )
        (x1, x2) = (min(x1, x2), max(x1, x2))
        (y1, y2) = (min(y1, y2), max(y1, y2))
        mx1 = min(mx1, x1)
        my1 = min(my1, y1)
        mx2 = max(mx2, x2)
        my2 = max(my2, y2)
    rect = ((mx1, my1), (mx2, my2))
    return rect


class PdfWordBox(object):
    def __init__(self, content, position):
        self.content = content
        self.position = minmax_rects(position)

    def __str__(self):
        return "{{ .position={}, .content={} }}".format(
            self.position, str(self.content)
        )

    def __lt__(self, o):
        return self.position < o.position

    def __repr__(self):
        return str(self)


class PdfLineBox(object):
    def __init__(self, word_boxes, position):
        self.word_boxes = word_boxes
        self.position = minmax_rects(position)

    def __str__(self):
        return "{{ .position={}, .word_boxes={} }}".format(
            self.position, str(self.word_boxes)
        )

    def __repr__(self):
        return str(self)

    def _get_content(self):
        return " ".join([w.content for w in self.word_boxes])

    content = property(_get_content)


class PdfPageMapping(object):
    SEPARATOR = ","

    def __init__(self, plugin, doc_url):
        self.plugin = plugin
        self.core = plugin.core
        self.doc_url = doc_url

        self.map_url = self.core.call_success(
            "fs_join", self.doc_url, MAPPING_FILE
        )

        self.mapping = None
        self.reverse_mapping = None
        self.page_mtimes = None

        self.nb_pages = -1
        self.real_nb_pages = -1

    def set_mapping(self, original_page_idx, target_page_idx):
        """
        Indicates that the page 'original_page_idx' in the actual PDF file
        is displayed as being the page 'target_page_idx'.
        If 'target_page_idx' < 0, it means the page is not displayed anymore
        (--> act if it is deleted)
        """
        if original_page_idx >= self.real_nb_pages:
            # comes from another set of plugins, no point in tracking it
            return

        now = datetime.datetime.now().timestamp()

        if target_page_idx is not None:
            old_original = self.reverse_mapping.get(target_page_idx, None)
            if old_original is not None and old_original in self.mapping:
                self.mapping.pop(old_original)

        old_target = self.mapping.get(original_page_idx, None)
        if old_target is not None and old_target in self.reverse_mapping:
            self.reverse_mapping.pop(old_target)
            self.page_mtimes[old_target] = now

        if target_page_idx is None and original_page_idx in self.mapping:
            self.mapping.pop(original_page_idx)
        else:
            self.mapping[original_page_idx] = target_page_idx

        if target_page_idx is not None:
            self.reverse_mapping[target_page_idx] = original_page_idx
            self.page_mtimes[target_page_idx] = now

    def update_nb_pages(self):
        self.nb_pages = 0
        if len(self.mapping) <= 0:
            return
        for v in self.mapping.values():
            if v is None:
                continue
            if v >= self.nb_pages:
                self.nb_pages = v + 1

    def load(self):
        try:
            self.real_nb_pages = self.plugin._doc_internal_get_nb_pages_by_url(
                self.doc_url, mapping=False
            )

            self.mapping = {p: p for p in range(0, self.real_nb_pages)}
            self.reverse_mapping = {p: p for p in range(0, self.real_nb_pages)}
            now = datetime.datetime.now().timestamp()
            self.page_mtimes = {p: now for p in range(0, self.real_nb_pages)}
            if self.core.call_success("fs_exists", self.map_url) is None:
                self.update_nb_pages()
                return

            with self.core.call_success("fs_open", self.map_url, "r") as fd:
                # drop the first line
                lines = fd.readlines()[1:]
                lines = [line.split(",", 1) for line in lines]
                lines = [
                    (int(orig_page_idx), int(target_page_idx))
                    for (orig_page_idx, target_page_idx) in lines
                ]
                lines.sort()
                for (orig_page_idx, target_page_idx) in lines:
                    if target_page_idx < 0:
                        target_page_idx = None
                    self.set_mapping(orig_page_idx, target_page_idx)

            self.update_nb_pages()
        except Exception as exc:
            LOGGER.critical(
                "Failed to load page mapping for doc %s !",
                self.doc_url, exc_info=exc
            )
            raise

    def load_reverse_only(self):
        """
        Load the mapping, but doesn't look at the total number of pages
        in the document. Avoid opening the PDF file.
        """
        self.mapping = None
        self.reverse_mapping = {}

        if self.core.call_success("fs_exists", self.map_url) is None:
            return

        with self.core.call_success("fs_open", self.map_url, "r") as fd:
            # drop the first line
            lines = fd.readlines()[1:]
            for line in lines:
                (orig_page_idx, target_page_idx) = line.split(",", 1)
                orig_page_idx = int(orig_page_idx)
                target_page_idx = int(target_page_idx)
                if target_page_idx < 0:
                    continue
                self.reverse_mapping[target_page_idx] = orig_page_idx

    def save(self):
        if self.core.call_success("fs_isdir", self.doc_url) is None:
            return

        nb_maps = 0
        for (orig_page_idx, target_page_idx) in self.mapping.items():
            if orig_page_idx == target_page_idx:
                continue
            nb_maps += 1

        if nb_maps <= 0:
            if self.core.call_success("fs_exists", self.map_url) is not None:
                self.core.call_success("fs_unlink", self.map_url)
            return

        with self.core.call_success("fs_open", self.map_url, "w") as fd:
            fd.write("original_page_index,target_page_index\n")
            mapping = list(self.mapping.items())
            mapping.sort()
            for (orig_page_idx, target_page_idx) in mapping:
                if orig_page_idx == target_page_idx:
                    continue
                fd.write("{},{}\n".format(orig_page_idx, target_page_idx))

            for page_idx in range(0, self.real_nb_pages):
                if page_idx not in self.mapping:
                    fd.write("{},-1\n".format(page_idx))

    def has_original_page_idx(self, original_page_idx):
        if self.mapping is None:
            self.load()
        return original_page_idx in self.mapping

    def get_original_page_idx(self, target_page_idx, reverse_only=False):
        if reverse_only:
            if self.reverse_mapping is None:
                self.load_reverse_only()
        else:
            if self.mapping is None:
                self.load()
        # Keep in mind we may have loaded only the mapping --> we don't know
        # how many pages there are in the PDF, so the mapping may be incomplete
        original_page_idx = self.reverse_mapping.get(target_page_idx, None)
        return original_page_idx

    def get_target_page_mtime(self, target_page_idx):
        if self.mapping is None:
            self.load()
        return self.page_mtimes.get(target_page_idx, None)

    def get_target_page_hash(self, target_page_idx):
        if self.mapping is None:
            self.load()
        original_page_idx = self.reverse_mapping.get(
            target_page_idx, None
        )
        if original_page_idx is None:
            return None
        return hash(original_page_idx)

    def _move_pages(self, original_page_idx, target_page_idx, offset):
        mapping = list(self.mapping.items())
        mapping.sort(key=lambda x: x[1], reverse=offset > 0)
        for (original, target) in mapping:
            if target >= target_page_idx:
                LOGGER.info(
                    "Page %d (original) ; target: %d --> %d",
                    original, target, target + offset
                )
                self.set_mapping(original, target + offset)

        self.update_nb_pages()

    def delete_target_page(self, target_page_idx):
        if self.mapping is None:
            self.load()

        LOGGER.info(
            "Deleting page %d from PDF %s",
            target_page_idx, self.doc_url
        )
        original_page_idx = self.reverse_mapping.pop(
            target_page_idx, None
        )
        if original_page_idx is not None:
            self.mapping.pop(original_page_idx, None)
        else:
            original_page_idx = target_page_idx

        self._move_pages(original_page_idx, target_page_idx, offset=-1)

    def make_room_for_target_page(self, target_page_idx):
        if self.mapping is None:
            self.load()
        original_page_idx = self.reverse_mapping.get(
            target_page_idx, target_page_idx
        )
        self._move_pages(original_page_idx, target_page_idx, offset=1)

    def print_mapping(self):
        if self.mapping is None:
            self.load()

        nb_pages = self.plugin._doc_internal_get_nb_pages_by_url(
            self.doc_url, mapping=False
        )

        print("==== MAPPING OF {} (nb_pages={}|{}) ====".format(
            self.doc_url, nb_pages, self.nb_pages
        ))
        for original_page_idx in range(0, nb_pages):
            target_page_idx = self.mapping.get(original_page_idx, None)
            if target_page_idx is None:
                print("{} --> {}".format(original_page_idx, original_page_idx))
                continue
            print("{} --> {}".format(original_page_idx, target_page_idx))
            if target_page_idx < 0:
                continue
            if target_page_idx not in self.reverse_mapping:
                print("WARNING: NO REVERSE")
            else:
                if original_page_idx != self.reverse_mapping[target_page_idx]:
                    print("WARNING: REVERSE DOESN'T MATCH: {} <-- {}".format(
                        target_page_idx, original_page_idx
                    ))
        print("=======================")

    def get_map_hash(self):
        if self.core.call_success("fs_exists", self.map_url) is None:
            return None
        return self.core.call_success("fs_hash", self.map_url)

    def get_map_mtime(self):
        if self.core.call_success("fs_exists", self.map_url) is None:
            return None
        return self.core.call_success("fs_get_mtime", self.map_url)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 20

    def __init__(self):
        super().__init__()
        # we cache the hash of PDF files since they never change
        self.cache_hash = {}
        # we cache the number of pages in PDF files since they never change
        # (real number before mapping)
        self.cache_nb_pages = {}

        self.cache_mappings = {}
        self.cache_passwords = {}

    def get_interfaces(self):
        return [
            "doc_hash",
            "doc_pdf",
            "doc_pdf_import",
            "doc_pdf_url",
            "doc_text",
            "doc_type",
            "page_boxes",
            "page_img",
            "page_paper",
            'pages',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                # to provide doc_get_nb_pages_by_url()
                'interface': 'nb_pages',
                'defaults': ['paperwork_backend.model'],
            },
            # for page_move_by_url():
            {
                'interface': 'pillow',
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
            {
                'interface': 'poppler',
                'defaults': ['paperwork_backend.poppler.memory'],
            },
            {
                'interface': 'urls',
                'defaults': ['openpaperwork_core.urls'],
            },
        ]

    def _get_pdf_url(self, doc_url):
        if doc_url.endswith(".pdf"):
            return doc_url
        pdf_url = self.core.call_success("fs_join", doc_url, PDF_FILENAME)
        if self.core.call_success("fs_exists", pdf_url) is None:
            return None
        return pdf_url

    def _get_pdf_password(self, doc_url):
        password = self.cache_passwords.get(doc_url, None)
        if password is not None:
            return password

        passwd_url = self.core.call_success(
            "fs_join", doc_url, PASSWD_FILENAME
        )
        if self.core.call_success("fs_exists", passwd_url):
            with self.core.call_success("fs_open", passwd_url, "r") as fd:
                password = fd.read().strip()
        self.cache_passwords[doc_url] = password
        return password

    def _get_page_mapping(self, doc_url):
        if doc_url in self.cache_mappings:
            return self.cache_mappings[doc_url]
        mapping = PdfPageMapping(self, doc_url)
        self.cache_mappings[doc_url] = mapping
        return mapping

    def _open_pdf(self, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return (None, None)

        password = self._get_pdf_password(doc_url)
        LOGGER.info("Opening %s (password=%s)", pdf_url, bool(password))
        doc = self.core.call_success(
            "poppler_open", pdf_url, password=password
        )
        return (pdf_url, doc)

    def is_doc(self, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        return True

    def doc_get_pdf_url_by_url(self, doc_url, write=False, allow_mapped=False):
        if write:
            return self.core.call_success("fs_join", doc_url, PDF_FILENAME)
        if not allow_mapped:
            mapping_url = self.core.call_success(
                "fs_join", doc_url, MAPPING_FILE
            )
            if self.core.call_success("fs_exists", mapping_url):
                return None
        return self._get_pdf_url(doc_url)

    def flush_doc_cache(self, doc_url):
        self.cache_hash.pop(doc_url, None)
        self.cache_passwords.pop(doc_url, None)
        self.cache_mappings.pop(doc_url, None)
        self.cache_nb_pages.pop(doc_url, None)

    def doc_get_hash_by_url(self, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return

        # cache the hash of doc.pdf to speed up imports
        if doc_url not in self.cache_hash:
            h = self.core.call_success("fs_hash", pdf_url)
            self.cache_hash[doc_url] = h
        return self.cache_hash[doc_url]

    def page_internal_get_hash_by_url(self, out: list, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return
        mapping = self._get_page_mapping(doc_url)
        page_hash = mapping.get_target_page_hash(page_idx)
        if page_hash is None:
            # deleted page or handled by another plugin
            return
        out.append(page_hash)

        # cache the hash of doc.pdf to speed up imports
        if doc_url not in self.cache_hash:
            h = self.core.call_success("fs_hash", pdf_url)
            self.cache_hash[doc_url] = h
        out.append(self.cache_hash[doc_url])

    def doc_internal_get_mtime_by_url(self, out: list, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        mapping = self._get_page_mapping(doc_url)
        mtime = mapping.get_map_mtime()
        if mtime is not None:
            out.append(mtime)

        mtime = self.core.call_success("fs_get_mtime", pdf_url)
        if mtime is None:
            return None
        out.append(mtime)

    def page_internal_get_mtime_by_url(self, out: list, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return

        mapping = self._get_page_mapping(doc_url)
        mtime = mapping.get_target_page_mtime(page_idx)
        if mtime is not None:
            out.append(mtime)

        mtime = self.core.call_success("fs_get_mtime", pdf_url)
        if mtime is not None:
            out.append(mtime)
        return

    def _doc_get_real_nb_pages_by_url(self, doc_url):
        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return None
        nb_pages = pdf.get_n_pages()
        return nb_pages

    def doc_pdf_get_real_nb_pages_by_url(self, doc_url):
        # Poppler is not thread-safe
        return self.core.call_one(
            "mainloop_execute", self._doc_get_real_nb_pages_by_url, doc_url
        )

    def _doc_internal_get_nb_pages_by_url(
            self, doc_url, mapping=True):
        if mapping:
            pdf_url = self._get_pdf_url(doc_url)
            if pdf_url is None:
                return 0
            mapping = self._get_page_mapping(doc_url)
            if mapping.nb_pages < 0:
                mapping.load()
            return mapping.nb_pages

        if doc_url in self.cache_nb_pages:
            r = self.cache_nb_pages[doc_url]
        else:
            r = self.doc_pdf_get_real_nb_pages_by_url(doc_url)
            if r is not None:
                self.cache_nb_pages[doc_url] = r
        return r if r is not None else 0

    def doc_internal_get_nb_pages_by_url(self, out: list, doc_url):
        r = self._doc_internal_get_nb_pages_by_url(doc_url)
        if r == 0:
            return
        out.append(r)

    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        if write:
            return None
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None

        # The first page is requested much more often than the others, due
        # to thumbnailing.
        # ASSUMPTION(Jflesch): If there is a doc.pdf, there is a first page
        # in it.
        # We don't want to open the PDF file for each thumbnail (first page)
        # but at the same time, we still need to check the mapping file.

        mapping = self._get_page_mapping(doc_url)
        original_page_idx = mapping.get_original_page_idx(
            page_idx, reverse_only=(page_idx == 0)
        )
        if original_page_idx is None:
            if page_idx != 0 and page_idx >= mapping.nb_pages:
                return None
            original_page_idx = page_idx

        password = self._get_pdf_password(doc_url)
        if password is not None:
            password = password.encode("utf-8").hex()

        # same URL used in browsers
        url = self.core.call_success(
            "url_args_join", pdf_url,
            page=str(original_page_idx + 1),
            password=password
        )
        return url

    @staticmethod
    def _custom_split(input_str, input_rects, splitter, log_txt):
        # turn text and layout from Poppler into boxes
        # XXX(Jflesch): following assert fails sometimes ? oO
        # assert len(input_str) == len(input_rects)
        if len(input_str) != len(input_rects):
            LOGGER.warning(
                "%s: Input strings: %d ; Input rects: %d",
                log_txt, len(input_str), len(input_rects)
            )
            m = min(len(input_str), len(input_rects))
            input_str = input_str[:m]
            input_rects = input_rects[:m]
        input_el = zip(input_str, input_rects)
        for (is_split, group) in itertools.groupby(
                    input_el,
                    lambda x: splitter(x[0])
                ):
            if is_split:
                continue
            letters = ""
            rects = []
            for (letter, rect) in group:
                letters += letter
                rects.append(rect)
            yield (letters, rects)

    def _doc_get_text_by_url(self, out: list, doc_url):
        task = "pdf_get_text_by_url({})".format(doc_url)
        self.core.call_all("on_perfcheck_start", task)

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            self.core.call_all("on_perfcheck_stop", task)
            return
        mapping = self._get_page_mapping(doc_url)

        for page_idx in range(0, pdf.get_n_pages()):
            if not mapping.has_original_page_idx(page_idx):
                continue
            page = pdf.get_page(page_idx)
            # some PDF are really badly damaged
            if page is None:
                continue
            try:
                txt = page.get_text()
                txt = txt.strip()
            except UnicodeDecodeError as exc:
                LOGGER.warning(
                    "%s p%d: UnicodeDecodeError: Assuming page has no text",
                    doc_url, page_idx, exc_info=exc
                )
                continue
            if txt == "":
                continue
            out.append(txt)
        self.core.call_all(
            "on_perfcheck_stop", task, nb_pages=pdf.get_n_pages()
        )
        return True

    def doc_get_text_by_url(self, out: list, doc_url):
        # Poppler is not thread-safe
        return self.core.call_one(
            "mainloop_execute",
            self._doc_get_text_by_url, out, doc_url
        )

    def _page_has_text_by_url(self, doc_url, page_idx):
        if doc_url in self.cache_nb_pages:
            if page_idx >= self.cache_nb_pages[doc_url]:
                return None

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return None

        page = pdf.get_page(page_idx)
        if page is None:
            return None

        try:
            return len(page.get_text().strip()) > 0
        except UnicodeDecodeError as exc:
            LOGGER.warning(
                "%s p%d: UnicodeDecodeError: Assuming page has no text",
                doc_url, page_idx, exc_info=exc
            )
            return False

    def page_has_text_by_url(self, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        mapping = self._get_page_mapping(doc_url)
        page_idx = mapping.get_original_page_idx(page_idx)
        if page_idx is None:
            return None
        # Poppler is not thread-safe
        return self.core.call_one(
            "mainloop_execute", self._page_has_text_by_url, doc_url, page_idx
        )

    def _page_get_text_by_url(self, doc_url, page_idx):
        if doc_url in self.cache_nb_pages:
            if page_idx >= self.cache_nb_pages[doc_url]:
                return None

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return None

        page = pdf.get_page(page_idx)
        if page is None:
            return None

        try:
            return page.get_text().strip()
        except UnicodeDecodeError as exc:
            LOGGER.warning(
                "%s p%d: UnicodeDecodeError: Assuming page has no text",
                doc_url, page_idx, exc_info=exc
            )
            return False

    def page_get_text_by_url(self, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        mapping = self._get_page_mapping(doc_url)
        page_idx = mapping.get_original_page_idx(page_idx)
        if page_idx is None:
            return None
        # Poppler is not thread-safe
        return self.core.call_one(
            "mainloop_execute", self._page_get_text_by_url, doc_url, page_idx
        )

    def _page_get_boxes_by_url(self, doc_url, page_idx):
        if doc_url in self.cache_nb_pages:
            if page_idx >= self.cache_nb_pages[doc_url]:
                return None

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return

        pdf_page = pdf.get_page(page_idx)
        if pdf_page is None:
            return

        try:
            txt = pdf_page.get_text()
            if txt.strip() == "":
                return None
        except UnicodeDecodeError as exc:
            LOGGER.warning(
                "%s p%d: UnicodeDecodeError: Assuming page has no text",
                doc_url, page_idx, exc_info=exc
            )
            return None

        layout = pdf_page.get_text_layout()
        if not layout[0]:
            return None
        layout = layout[1]

        line_boxes = []
        for (line, line_rects) in self._custom_split(
                    txt, layout, lambda x: x == "\n", "lines",
                ):
            words = []
            for (word, word_rects) in self._custom_split(
                        line, line_rects, lambda x: x.isspace(), "words"
                    ):
                word_box = PdfWordBox(word, word_rects)
                words.append(word_box)
            line_boxes.append(PdfLineBox(words, line_rects))
        return line_boxes

    def page_get_boxes_by_url(self, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        mapping = self._get_page_mapping(doc_url)
        page_idx = mapping.get_original_page_idx(page_idx)
        if page_idx is None:
            return None
        # Poppler is not thread-safe
        return self.core.call_one(
            "mainloop_execute", self._page_get_boxes_by_url, doc_url, page_idx
        )

    def doc_pdf_import(self, src_file_uri, password=None, target_doc_id=None):
        doc_id = None
        doc_url = None

        if target_doc_id is not None:
            doc_id = target_doc_id
            doc_url = self.core.call_success(
                "doc_id_to_url", doc_id, existing=False
            )
            if doc_url is None:
                doc_id = None
            elif self.core.call_success("fs_exists", doc_url):
                doc_id = None

        if doc_id is None:
            (doc_id, doc_url) = self.core.call_success("storage_get_new_doc")

        # just to be safe
        self.cache_mappings.pop(doc_url, None)

        pdf_url = self.core.call_success("fs_join", doc_url, PDF_FILENAME)

        self.core.call_success("fs_mkdir_p", doc_url)
        self.core.call_success("fs_copy", src_file_uri, pdf_url)

        if password is not None:
            passwd_url = self.core.call_success(
                "fs_join", doc_url, PASSWD_FILENAME
            )
            with self.core.call_success("fs_open", passwd_url, "w") as fd:
                fd.write(password)

        try:
            # check the PDF is readable
            doc = self.core.call_success(
                "poppler_open", pdf_url, password=password
            )
            exc_info = None
        except Exception as exc:
            doc = None
            exc_info = exc

        if doc is None:
            if exc_info is None:
                LOGGER.error("Failed to read %s", pdf_url)
            else:
                LOGGER.error("Failed to read %s", pdf_url, exc_info=exc_info)
            self.core.call_success("fs_rm_rf", doc_url, trash=False)
            return (None, None)

        return (doc_id, doc_url)

    def page_delete_by_url(self, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return
        mapping = self._get_page_mapping(doc_url)
        mapping.delete_target_page(page_idx)
        mapping.save()

    def _page_get_paper_size_by_url(self, doc_url, page_idx):
        if doc_url in self.cache_nb_pages:
            if page_idx >= self.cache_nb_pages[doc_url]:
                return None

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return None

        page = pdf.get_page(page_idx)
        if page is None:
            return

        size = page.get_size()

        # points --> inches: / 72
        # inches --> millimeters (i18n unit): * 25.4
        return (
            size[0] / 72.0 * 25.4,
            size[0] / 72.0 * 25.4,
        )

    def page_get_paper_size_by_url(self, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        mapping = self._get_page_mapping(doc_url)
        page_idx = mapping.get_original_page_idx(page_idx)
        if page_idx is None:
            return None
        # Poppler is not thread-safe
        return self.core.call_one(
            "mainloop_execute",
            self._page_get_paper_size_by_url, doc_url, page_idx
        )

    def page_move_by_url(
                self,
                source_doc_url, target_source_page_idx,
                dest_doc_url, target_dest_page_idx
            ):
        # 'source' is about the source document.
        # 'dest' is about the destination document.
        # 'original' is about the original position of a page in a PDF file.
        # 'target' is about the position of a page as shown to the end-user.

        source_pdf_url = self._get_pdf_url(source_doc_url)
        source_is_pdf = source_pdf_url is not None
        dest_is_pdf = self._get_pdf_url(dest_doc_url) is not None
        if not source_is_pdf and not dest_is_pdf:
            return

        if source_is_pdf:
            source_mapping = self._get_page_mapping(source_doc_url)
        if dest_is_pdf:
            dest_mapping = self._get_page_mapping(dest_doc_url)

        LOGGER.info(
            "%s (%s) p%d --> %s (%s) p%d",
            source_doc_url, "PDF" if source_is_pdf else "non-PDF",
            target_source_page_idx,
            dest_doc_url, "PDF" if dest_is_pdf else "non-PDF",
            target_dest_page_idx,
        )

        if source_is_pdf:
            original_source_page_idx = source_mapping.get_original_page_idx(
                target_source_page_idx
            )
            # if original_source_page_idx is None means
            # this page is not handled by us ; still, we must shift
            # all our pages
            LOGGER.info(
                "- Removing page (original=%s, target=%d) from %s",
                original_source_page_idx, target_source_page_idx,
                source_doc_url
            )
            source_mapping.delete_target_page(target_source_page_idx)

        if dest_is_pdf:
            LOGGER.info(
                "- Making room for a new page (target=%d) in %s",
                target_dest_page_idx, dest_doc_url
            )
            dest_mapping.make_room_for_target_page(target_dest_page_idx)

        if source_doc_url == dest_doc_url:
            assert source_mapping is dest_mapping
            if original_source_page_idx is not None:
                LOGGER.info(
                    "New mapping: %s: original=p%d --> target=p%d",
                    source_doc_url, original_source_page_idx,
                    target_dest_page_idx
                )
                source_mapping.set_mapping(
                    original_source_page_idx, target_dest_page_idx
                )

                source_mapping.update_nb_pages()
        elif source_is_pdf:
            if original_source_page_idx is not None:
                # export the PDF page as an image file
                # it relies on other model plugins (interface 'page_img'), but
                # they can't be declared as dependencies, as we do provide
                # 'page_img' too. It would make a dependency loop.

                # we are a low priority plugin: other plugins should
                # already have made room for our page if required

                source_img = "{}#page={}".format(
                    source_pdf_url, str(original_source_page_idx + 1)
                )
                LOGGER.info("Generating image from %s", source_img)
                source_img = self.core.call_success(
                    "url_to_pillow", source_img
                )

                # since PDF are not writable by themselves, we can call
                # page_get_img_url(write=True). We are sure that our
                # implementation of this method won't reply
                dest_img = self.core.call_success(
                    "page_get_img_url", dest_doc_url, target_dest_page_idx,
                    write=True, original=True
                )
                LOGGER.info("Writting page image back as %s", dest_img)
                self.core.call_success("pillow_to_url", source_img, dest_img)

        if source_is_pdf:
            source_mapping.save()
        if dest_is_pdf:
            dest_mapping.save()
