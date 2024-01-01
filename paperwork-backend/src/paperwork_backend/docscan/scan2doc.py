import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.scan_id_to_doc_id = {}
        self.doc_id_to_scan_id = {}

    def get_interfaces(self):
        return ['scan2doc']

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': 'page_img',
                'defaults': ['paperwork_backend.model.img'],
            },
            {
                'interface': 'pillow',
                'defaults': ['openpaperwork_core.pillow.img'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def scan2doc_scan_id_to_doc_id(self, scan_id):
        try:
            return self.scan_id_to_doc_id[scan_id]
        except KeyError:
            return None

    def scan2doc_doc_id_to_scan_id(self, doc_id):
        try:
            return self.doc_id_to_scan_id[doc_id]
        except KeyError:
            return None

    def scan2doc_promise(self, *args, doc_id=None, doc_url=None, **kwargs):
        """
        The promise returned by this method should be scheduled with
        scan_schedule() to avoid any possible conflict with another
        scan (or scanner lookup).
        """
        if doc_id is not None and doc_url is not None:
            nb_pages = self.core.call_success(
                "doc_get_nb_pages_by_url", doc_url
            )
            new = (nb_pages <= 0) if nb_pages is not None else True
        else:
            (doc_id, doc_url) = self.core.call_success("storage_get_new_doc")
            new = True

        (scan_id, p) = self.core.call_success("scan_promise", *args, **kwargs)

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all,
            args=("on_scan2doc_start", scan_id, doc_id, doc_url)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(p)

        self.scan_id_to_doc_id[scan_id] = doc_id
        self.doc_id_to_scan_id[doc_id] = scan_id

        def add_scans_to_doc(args):
            (source, scan_id, imgs) = args
            nb = 0
            for img in imgs:
                nb += 1
                nb_pages = self.core.call_success(
                    "doc_get_nb_pages_by_url", doc_url
                )
                if nb_pages is None:
                    nb_pages = 0
                page_url = self.core.call_success(
                    "page_get_img_url", doc_url, nb_pages, write=True
                )
                self.core.call_success("pillow_to_url", img, page_url)
                self.core.call_all(
                    "mainloop_schedule", self.core.call_all,
                    "on_scan2doc_page_scanned",
                    scan_id, doc_id, doc_url, nb_pages
                )
            return nb

        def drop_scan_id(scan_id, doc_id):
            self.scan_id_to_doc_id.pop(scan_id, None)
            self.doc_id_to_scan_id.pop(doc_id, None)

        def notify_end(scan_id, doc_id):
            self.core.call_all("on_scan2doc_end", scan_id, doc_id, doc_url)
            return (doc_id, doc_url)

        def cancel(exc, scan_id, doc_id):
            drop_scan_id(scan_id, doc_id)
            if new:
                self.core.call_all("storage_delete_doc_id", doc_id)
            raise exc

        def run_transactions(nb_imgs, scan_id, doc_id):
            # start a second promise chain, but scheduled with
            # "transaction_schedule()"
            promise = openpaperwork_core.promise.Promise(
                self.core, drop_scan_id, args=(scan_id, doc_id)
            )
            promise = promise.then(self.core.call_success(
                "transaction_simple_promise",
                [("add" if new else "upd", doc_id),]
            ))
            promise = promise.then(notify_end, scan_id, doc_id)
            promise = promise.catch(cancel, scan_id, doc_id)
            self.core.call_success("transaction_schedule", promise)
            return (doc_id, doc_url)

        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, add_scans_to_doc
            )
        )
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, run_transactions, args=(scan_id, doc_id)
            )
        )
        promise = promise.catch(cancel, scan_id, doc_id)
        return promise
