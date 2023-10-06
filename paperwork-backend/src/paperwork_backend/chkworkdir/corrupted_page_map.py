from typing import List
from typing import Tuple
import logging
import re

import openpaperwork_core
import paperwork_backend.model.pdf

from .. import _


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_REGEX = re.compile(r"paper\.(\d+)\.(.*)")
PAGE_FILENAME_FMT = "paper.{idx}.{file_ext}"


class Plugin(openpaperwork_core.PluginBase):
    """
    Label files in each document contains both the label names and their color.
    If the user changes a label color, label files are updated one-by-one.
    If this process is interrupted, we end up with 2 colors for the same
    label.
    """

    PRIORITY = 10000

    def get_interfaces(self):
        return ['chkworkdir']

    def get_deps(self):
        return [
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'doc_pdf_url',
                'defaults': ['paperwork_backend.model.pdf'],
            },
        ]

    def check_work_dir(self, out_problems: list):
        all_docs: List[Tuple[str, str]] = []
        self.core.call_all("storage_get_all_docs", all_docs, only_valid=False)
        all_docs.sort()

        total = len(all_docs)
        LOGGER.info("Checking work directory (%d documents)", total)

        for (idx, (doc_id, doc_url)) in enumerate(all_docs):
            self.core.call_all(
                "on_progress", "chkworkdir_corrupted_page_map",
                idx / total, _("Checking doc %s") % (doc_id,)
            )

            page_map_url = self.core.call_success(
                "fs_join", doc_url,
                paperwork_backend.model.pdf.PdfPageMapping.MAPPING_FILE
            )
            if not self.core.call_success("fs_exists", page_map_url):
                continue

            # simplest way to see if the page map is readable is to
            # try to get the number of pages of the doc
            try:
                self.core.call_success("doc_get_nb_pages_by_url", doc_url)
                continue
            except Exception:
                out_problems.append({
                    "problem": "corrupted_page_map",
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "human_description": {
                        "problem": (
                            _(
                                "Page mapping of document %s has been"
                                " corrupted"
                            ) % (doc_id,)
                        ),
                        "solution": (
                            _(
                                "Page mapping of document %s must be"
                                " reinitialized"
                            ) % (doc_id,)
                        )
                    }
                })

        self.core.call_all("on_progress", "chkworkdir_corrupted_page_map", 1.0)

    def fix_work_dir(self, problems):
        total = len(problems)
        for (idx, problem) in enumerate(problems):
            if problem['problem'] != 'corrupted_page_map':
                continue
            doc_id = problem['doc_id']
            doc_url = problem['doc_url']
            LOGGER.info("Fixing document %s", doc_url)
            self.core.call_all(
                "on_progress", "fixworkdir_corrupted_page_map",
                idx / total,
                _("Fixing page mapping of doc %s") % (doc_id,)
            )
            page_map_url = self.core.call_success(
                "fs_join", doc_url,
                paperwork_backend.model.pdf.PdfPageMapping.MAPPING_FILE
            )
            if self.core.call_success("fs_exists", page_map_url):
                self.core.call_success("fs_unlink", page_map_url)

            # Move all the scanned page files after the PDF pages
            doc_nb_pages = self.core.call_success(
                "doc_pdf_get_real_nb_pages_by_url", doc_url
            )
            page_map = {}
            files = self.core.call_success("fs_listdir", doc_url)
            if files is None:
                return None
            for file_url in files:
                file_name = self.core.call_success("fs_basename", file_url)
                match = PAGE_FILENAME_REGEX.match(file_name)
                if match is None:
                    continue
                old_page_nb = int(match.group(1))
                file_ext = match.group(2)
                if old_page_nb in page_map:
                    new_page_nb = page_map[old_page_nb]
                else:
                    new_page_nb = doc_nb_pages + 1
                    doc_nb_pages += 1
                    page_map[old_page_nb] = new_page_nb
                new_page_url = self.core.call_success(
                    "fs_join", doc_url, PAGE_FILENAME_FMT.format(
                        idx=new_page_nb,
                        file_ext=file_ext
                    )
                )
                self.core.call_success("fs_rename", file_url, new_page_url)

        self.core.call_all("on_progress", "fixworkdir_corrupted_page_map", 1.0)
