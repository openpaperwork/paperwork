import rich.layout
import rich.padding
import rich_pixels

import openpaperwork_core


class RichPixelsRenderer(object):
    def __init__(self, plugin):
        self.plugin = plugin
        self.core = plugin.core
        self.parent = None

    def get_preview_output(
                self, doc_id, doc_url, terminal_size=(80, 25),
                page_idx=0
            ):
        w_split = int(terminal_size[0] / 3)

        parent = []
        if self.parent is not None:
            parent = self.parent.get_preview_output(
                doc_id, doc_url,
                (terminal_size[0] - w_split - 2, terminal_size[1]),
                page_idx
            )

        thumbnail = self.core.call_success(
            "thumbnail_get_page", doc_url, page_idx
        )
        if thumbnail is not None:
            thumbnail = self.plugin.img_render(thumbnail, w_split)
            parent = rich.padding.Padding(parent, (0, 0, 0, 1))

        out = rich.layout.Layout()
        out.split_row(
            rich.layout.Layout(thumbnail, name="thumbnail"),
            rich.layout.Layout(parent, name="parent"),
        )
        out["parent"].ratio = 2

        out["thumbnail"].visible = bool(thumbnail)

        return [out]

    def get_doc_output(self, doc_id, doc_url, terminal_size=(80, 25)):
        out = []
        if self.parent is not None:
            out = self.parent.get_doc_output(
                doc_id, doc_url, terminal_size
            )
        return out

    def get_page_output(self, doc_id, doc_url, page_nb, terminal_size=(80, 25)):
        parent_out = []
        if self.parent is not None:
            parent_out = self.parent.get_page_output(
                doc_id, doc_url, page_nb, terminal_size
            )

        img_url = self.core.call_success("page_get_img_url", doc_url, page_nb)
        img = self.core.call_success("url_to_pillow", img_url)
        img = self.plugin.img_render(img, terminal_width=(terminal_size[0] - 1))
        return [img_url, img, "", *parent_out]

    def get_doc_infos(self, doc_id, doc_url):
        out = {}
        if self.parent is not None:
            out = self.parent.get_doc_infos(doc_id, doc_url)
        return out

    def get_page_infos(self, doc_id, doc_url, page_nb):
        out = {}
        if self.parent is not None:
            out = self.parent.get_page_infos(doc_id, doc_url, page_nb)
        out['image'] = self.core.call_success(
            "page_get_img_url", doc_url, page_nb
        )
        return out


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    @classmethod
    def get_interfaces(cls):
        return [
            'doc_renderer',
            'img_renderer',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'page_img',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
            {
                'interface': 'thumbnail',
                'defaults': ['paperwork_backend.model.thumbnail'],
            },
        ]

    def doc_renderer_get(self, out):
        r = RichPixelsRenderer(self)
        if len(out) > 0:
            r.parent = out[-1]
        out.append(r)

    def img_render(self, img, terminal_width=80):
        height = int(terminal_width * img.size[1] / img.size[0])
        img = rich_pixels.Pixels.from_image(img, resize=(terminal_width, height))
        return img
