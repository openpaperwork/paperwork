import logging
import re

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

MIN_WORD_LENGTH = 3
SPLIT = r"\W+"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    # those are keywords used in python-whoosh query syntax. There is no
    # point in highlighting them
    IGNORE_LIST = {"and", "or"}

    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_pageview_boxes_listener',
            'search_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_pageview',
                'defaults': ['paperwork_gtk.mainwindow.docview.pageview'],
            },
            {
                'interface': 'gtk_pageview_boxes',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageview.boxes'
                ],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.re_split = re.compile(SPLIT)
        self.keywords = set()

    def on_search_start(self, query):
        query = self.re_split.split(
            self.core.call_success("i18n_strip_accents", query)
        )
        self.keywords = {
            keyword.lower() for keyword in query
            if len(keyword) >= MIN_WORD_LENGTH
        }
        self.core.call_all("pageview_refresh_all")

    def on_search_results(self, query, docs):
        pass

    def on_page_draw(self, cairo_ctx, page):
        if len(self.keywords) <= 0:
            return

        boxes = self.core.call_success(
            "pageview_get_boxes_by_id", page.doc_id, page.page_idx
        )
        if boxes is None:
            return

        for line_box in boxes:
            for word_box in line_box.word_boxes:
                word = self.core.call_success(
                    "i18n_strip_accents", word_box.content
                )
                word = word.strip()
                if word.lower() in self.IGNORE_LIST:
                    continue
                for w in self.re_split.split(word):
                    w = w.lower()
                    if w not in self.keywords:
                        continue
                    self.core.call_all(
                        "page_draw_box",
                        cairo_ctx, page, word_box.position,
                        (0.0, 1.0, 0.0), border_width=2
                    )
