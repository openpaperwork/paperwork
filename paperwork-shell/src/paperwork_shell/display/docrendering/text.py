import openpaperwork_core

from paperwork_backend.interfaces.pages import PageText

from paperwork_shell.interfaces.renderer import AbstractDocRenderer
from paperwork_shell.interfaces.renderer import DocRendererFactory


PREVIEW_MAX_LINES = 25


class TextRenderer(AbstractDocRenderer):
    def __init__(self, core):
        self.core = core
        self.parent = None

    def _get_page_text(self, doc_url, page_nb):
        out = []
        line_boxes = self.core.call_success(
            PageText.page_get_boxes_by_url, doc_url, page_nb
        )
        if line_boxes is None:
            return out
        for line_box in line_boxes:
            line = line_box.content
            if line == "":
                continue
            out.append(line)
        return out

    def _rearrange_lines(self, lines, terminal_width):
        out = []
        for line in lines:
            new_line = ""
            iwords = line.split(" ")
            words = []
            for word in iwords:
                for p in range(0, len(word), terminal_width - 1):
                    words.append(word[p:p + terminal_width - 1])
            for word in words:
                if len(new_line) + len(word) + 1 >= terminal_width:
                    out.append(new_line)
                    new_line = ""
                new_line += " " + word
            if len(new_line.strip()) > 0:
                out.append(new_line)
        return [line.strip() for line in out]

    def get_preview_output(
                self, doc_id, doc_url, terminal_size=(80, 25),
                page_idx=0
            ):
        if self.parent is None:
            out = []
        else:
            out = self.parent.get_preview_output(
                doc_id, doc_url, terminal_size, page_idx
            )
        text = self._get_page_text(doc_url, page_idx)
        text = self._rearrange_lines(text, terminal_size[0])
        text = text[:PREVIEW_MAX_LINES]
        return out + text

    def get_doc_output(self, doc_id, doc_url, terminal_size=(80, 25)):
        if self.parent is None:
            out = []
        else:
            out = self.parent.get_doc_output(doc_id, doc_url, terminal_size)

        return out

    def get_page_output(
                self, doc_id, doc_url, page_nb, terminal_size=(80, 25)
            ):
        if self.parent is None:
            out = []
        else:
            out = self.parent.get_page_output(doc_id, doc_url, terminal_size)
        text = self._get_page_text(doc_url, page_nb)
        text = self._rearrange_lines(text, terminal_size[0])
        return out + text

    def get_doc_infos(self, doc_id, doc_url):
        out = {}
        if self.parent is not None:
            out = self.parent.get_doc_infos(doc_id, doc_url)
        out["doc_id"] = doc_id
        return out

    def get_page_infos(self, doc_id, doc_url, page_nb):
        out = {}
        if self.parent is not None:
            out = self.parent.get_page_infos(doc_id, doc_url, page_nb)
        out["text"] = self._get_page_text(doc_url, page_nb)
        return out


class Plugin(
    openpaperwork_core.PluginBase,
    DocRendererFactory,
):
    PRIORITY = 10000

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=PageText,
                defaults=[
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            ),
        ]

    def doc_renderer_get(self, out):
        r = TextRenderer(self.core)
        if len(out) > 0:
            r.parent = out[-1]
        out.append(r)
