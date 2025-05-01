import logging
import re

from openpaperwork_core.interfaces.i18n import I18n
import openpaperwork_core

from paperwork_gtk.interfaces.page_boxes import PageViewBoxes
from paperwork_gtk.interfaces.page_drawer import PageDrawer

from paperwork_gtk.interfaces.search_field import SearchResultsListener


LOGGER = logging.getLogger(__name__)

MIN_WORD_LENGTH = 3
SPLIT = r"\W+"


class Plugin(
    openpaperwork_core.PluginBase,
    PageDrawer,
    SearchResultsListener,
):
    PRIORITY = 100

    # those are keywords used in python-whoosh query syntax. There is no
    # point in highlighting them
    IGNORE_LIST = {"and", "or"}

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': PageViewBoxes,
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageview.boxes'
                ],
            },
            {
                'interface': I18n,
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.re_split = re.compile(SPLIT)
        self.keywords = set()

    def on_search_start(self, query):
        query = self.re_split.split(
            self.core.call_success(I18n.i18n_strip_accents, query)
        )
        self.keywords = {
            keyword.lower() for keyword in query
            if len(keyword) >= MIN_WORD_LENGTH
        }
        self.core.call_all(PageDrawer.pageview_refresh_all)

    @openpaperwork_core.noop
    def on_search_results(self, query, docs):
        pass

    def on_page_draw(self, cairo_ctx, page):
        if len(self.keywords) <= 0:
            return

        boxes = self.core.call_success(
            PageViewBoxes.pageview_get_boxes_by_id, page.doc_id, page.page_idx
        )
        if boxes is None:
            return

        for line_box in boxes:
            for word_box in line_box.word_boxes:
                word = self.core.call_success(
                    I18n.i18n_strip_accents, word_box.content
                )
                word = word.strip()
                if word.lower() in self.IGNORE_LIST:
                    continue
                for w in self.re_split.split(word):
                    w = w.lower()
                    if w not in self.keywords:
                        continue
                    self.core.call_all(
                        PageViewBoxes.page_draw_box,
                        cairo_ctx, page, word_box.position,
                        (0.0, 1.0, 0.0), border_width=2
                    )

    @openpaperwork_core.noop
    def pageview_refresh_all(self):
        pass

    @openpaperwork_core.noop
    def on_page_visibility_changed(self, page, visible):
        pass
