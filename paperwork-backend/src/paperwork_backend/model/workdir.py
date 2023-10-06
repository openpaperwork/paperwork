import datetime
import logging
import os

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

DOCNAME_FORMAT = "%Y%m%d_%H%M_%S"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -1000  # see page_delete_by_url() / page_move_by_url()

    def get_interfaces(self):
        return [
            "document_storage",
            "stats"
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
        ]

    def init(self, core):
        super().init(core)
        setting = self.core.call_success(
            "config_build_simple", "Global", "WorkDirectory",
            lambda: self.core.call_success(
                "fs_safe", os.path.expanduser("~/papers")
            )
        )
        self.core.call_all("config_register", "workdir", setting)
        self.core.call_all(
            "config_add_observer", "workdir", self._on_work_dir_changed
        )

    def _on_work_dir_changed(self):
        LOGGER.info("Work directory has changed")
        self.core.call_all("on_storage_changed")

    def storage_get_id(self):
        """
        Returns a string identifying the storage (work directory)
        currently used.

        Do not assume it's a valid directory path. For instance, this plugin
        could be replaced by a MariaDB database someday, and so the string
        would identify the database instead of a directory.
        """
        return self.core.call_success('config_get', 'workdir')

    def storage_get_all_docs(self, out: list, only_valid=True):
        """
        Returns all document IDs and URLs in the work directory
        """
        workdir = self.core.call_success('config_get', 'workdir')
        if self.core.call_success('fs_exists', workdir) is None:
            # we are not the plugin handling this storage (?)
            return
        LOGGER.info("Loading document list from %s", workdir)
        nb = 0
        for doc_url in self.core.call_success('fs_listdir', workdir):
            doc_id = self.core.call_success("fs_basename", doc_url)
            if doc_id.startswith("."):
                continue
            if only_valid and not self.core.call_success("fs_isdir", doc_url):
                LOGGER.warning(
                    "Ignoring document '%s': not a directory", doc_url
                )
                continue
            if (
                    only_valid and
                    self.core.call_success("is_doc", doc_url) is None):
                LOGGER.warning(
                    "Ignoring document '%s': not recognized document type",
                    doc_url
                )
                continue
            out.append((doc_id, doc_url))
            nb += 1
        LOGGER.info("%d documents found in %s", nb, workdir)

    def doc_id_to_url(self, doc_id, existing=True):
        assert doc_id is not None
        workdir = self.core.call_success('config_get', 'workdir')
        url = self.core.call_success("fs_join", workdir, doc_id)
        if existing and self.core.call_success("fs_isdir", url) is None:
            return None
        return url

    def doc_url_to_id(self, doc_url):
        workdir = self.core.call_success('config_get', 'workdir')
        if not doc_url.startswith(workdir):
            return None
        return self.core.call_success("fs_basename", doc_url)

    def doc_get_date_by_id(self, doc_id):
        # Doc id is expected to have this format:
        # YYYYMMDD_hhmm_ss_NN_something_else
        doc_id = doc_id.split("_", 3)
        doc_id = "_".join(doc_id[:3])
        try:
            return datetime.datetime.strptime(doc_id, DOCNAME_FORMAT)
        except ValueError:
            return None

    def doc_get_id_by_date(self, date):
        return date.strftime(DOCNAME_FORMAT)

    # datetime.datetime.now cannot be mocked with unittest.mock.patch
    # (datetime is built-in) --> allow dependency injection here
    def storage_get_new_doc(self, now_func=datetime.datetime.now):
        workdir = self.core.call_success('config_get', 'workdir')

        base_doc_id = now_func().strftime(DOCNAME_FORMAT)
        base_doc_url = self.core.call_success("fs_join", workdir, base_doc_id)

        doc_id = base_doc_id
        doc_url = base_doc_url
        doc_idx = 0

        while self.core.call_success("fs_exists", doc_url) is not None:
            doc_idx += 1
            doc_id = "{}_{}".format(base_doc_id, doc_idx)
            doc_url = "{}_{}".format(base_doc_url, doc_idx)

        return (doc_id, doc_url)

    def storage_delete_doc_id(self, doc_id, trash=True):
        doc_url = self.doc_id_to_url(doc_id)
        if doc_url is None:
            return
        self.core.call_success("fs_rm_rf", doc_url, trash=trash)

    def stats_get(self, stats):
        LOGGER.info("Counting documents for statistics...")
        all_docs = []
        self.storage_get_all_docs(all_docs)
        stats['nb_documents'] += len(all_docs)

    def page_delete_by_url(self, doc_url, page_idx):
        workdir = self.core.call_success('config_get', 'workdir')
        if not doc_url.startswith(workdir):
            return None
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is not None and nb_pages > 0:
            return
        LOGGER.warning(
            "All pages of document %s have been removed. Removing document",
            doc_url
        )
        self.core.call_success("fs_rm_rf", doc_url)

    def page_move_by_url(
                self,
                source_doc_url, source_page_idx,
                dest_doc_url, dest_page_idx
            ):
        workdir = self.core.call_success('config_get', 'workdir')
        if not source_doc_url.startswith(workdir):
            return None
        workdir = self.core.call_success('config_get', 'workdir')
        if not dest_doc_url.startswith(workdir):
            return None

        nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", source_doc_url
        )
        if nb_pages is not None and nb_pages > 0:
            return
        LOGGER.warning(
            "All pages of document %s have been removed. Removing document",
            source_doc_url
        )
        self.core.call_success("fs_rm_rf", source_doc_url)

    def doc_rename_by_url(self, src_doc_url, dst_doc_url):
        if not self.core.call_success("fs_isdir", src_doc_url):
            # May happen on integrated documentation PDF files
            LOGGER.warning("Cannot rename non-directory documents")
            return
        idx = 0
        dst_url = dst_doc_url
        while self.core.call_success("fs_exists", dst_url) is not None:
            idx += 1
            dst_url = "{}_{}".format(dst_doc_url, idx)
        self.core.call_success("fs_rename", src_doc_url, dst_url)
        return dst_url
