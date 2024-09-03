import openpaperwork_core

import rich.style
import rich.text


def color_labels(core, labels):
    for label, color in labels:
        bg_color = core.call_success("label_color_to_rgb", color)
        fg_color = core.call_success("label_get_foreground_color", bg_color)
        style = rich.style.Style(color='#%02x%02x%02x' % tuple(int(c * 0xFF) for c in fg_color),
                                 bgcolor='#%02x%02x%02x' % tuple(int(c * 0xFF) for c in bg_color))
        label = rich.text.Text(label, style=style)
        yield label


class LabelsRenderer(object):
    def __init__(self, core):
        self.core = core
        self.parent = None

    def _get_labels(self, doc_url):
        labels = set()
        self.core.call_all("doc_get_labels_by_url", labels, doc_url)
        return labels

    def _rearrange_labels(self, labels, terminal_width):
        text = rich.text.Text(" ").join(labels)
        text = text.wrap(None, terminal_width)
        return text

    def get_preview_output(
                self, doc_id, doc_url, terminal_size=(80, 25),
                page_idx=0
            ):
        out = []
        if self.parent is not None:
            out = self.parent.get_preview_output(
                doc_id, doc_url, terminal_size, page_idx
            )
        if page_idx != 0:
            return out

        labels = self._get_labels(doc_url)
        labels = color_labels(self.core, labels)
        labels = self._rearrange_labels(labels, terminal_size[0])
        labels.append(rich.text.Text("\n").join([rich.text.Text.from_ansi(line) for line in out]))
        return labels

    def get_doc_output(self, doc_id, doc_url, terminal_size=(80, 25)):
        out = []
        if self.parent is not None:
            out = self.parent.get_doc_output(
                doc_id, doc_url, terminal_size
            )

        labels = self._get_labels(doc_url)
        labels = color_labels(self.core, labels)
        labels = self._rearrange_labels(labels, terminal_size[0])
        labels.append(rich.text.Text("\n").join([rich.text.Text.from_ansi(line) for line in out]))
        return labels

    def get_page_output(
                self, doc_id, doc_url, page_nb, terminal_size=(80, 25)
            ):
        if self.parent is not None:
            return self.parent.get_page_output(
                doc_id, doc_url, page_nb, terminal_size
            )
        return []

    def get_doc_infos(self, doc_id, doc_url):
        out = {}
        if self.parent is not None:
            out = self.parent.get_doc_infos(doc_id, doc_url)
        out['labels'] = []
        for (label, color) in self._get_labels(doc_url):
            out['labels'].append(
                {
                    'label': label,
                    'color': color,
                }
            )
        return out

    def get_page_infos(self, doc_id, doc_url, page_nb):
        if self.parent is not None:
            return self.parent.get_page_infos(doc_id, doc_url, page_nb)
        return {}


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def get_interfaces(self):
        return ['doc_renderer']

    def get_deps(self):
        return [
            {
                'interface': 'page_boxes',
                'defaults': ['paperwork_backend.model.labels'],
            },
        ]

    def format_labels(self, labels, separator='\n'):
        labels = color_labels(self.core, labels)
        return rich.text.Text(separator).join(labels)

    def doc_renderer_get(self, out):
        r = LabelsRenderer(self.core)
        if len(out) > 0:
            r.parent = out[-1]
        out.append(r)
