import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['nb_pages']

    def doc_get_nb_pages_by_url(self, doc_url):
        out = []
        self.core.call_all("doc_internal_get_nb_pages_by_url", out, doc_url)
        r = max(out, default=0)
        if r == 0:
            return None
        return r

    def page_get_hash_by_url(self, doc_url, page_idx):
        out = []
        self.core.call_all(
            "page_internal_get_hash_by_url", out, doc_url, page_idx
        )
        r = 0
        for h in out:
            r ^= h
        return r

    def doc_get_mtime_by_url(self, doc_url):
        out = []
        self.core.call_all("doc_internal_get_mtime_by_url", out, doc_url)
        return max(out, default=None)

    def page_get_mtime_by_url(self, doc_url, page_idx):
        out = []
        self.core.call_all(
            "page_internal_get_mtime_by_url", out, doc_url, page_idx
        )
        return max(out, default=None)
