import logging

import openpaperwork_core

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    """
    Locates (and optionnally deletes) empty directories in the work
    directory.
    """
    def get_interfaces(self):
        return ['chkworkdir']

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'nb_pages',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
        ]

    def check_work_dir(self, out_problems: list):
        all_docs = []
        self.core.call_all("storage_get_all_docs", all_docs, only_valid=False)
        all_docs.sort()

        total = len(all_docs)
        LOGGER.info("Checking work directory (%d documents)", total)
        for (idx, (doc_id, doc_url)) in enumerate(all_docs):
            self.core.call_all(
                "on_progress", "chkworkdir_empty_doc",
                idx / total, _("Checking doc %s") % (doc_id,)
            )
            isdir = self.core.call_success("fs_isdir", doc_url)
            if not isdir:
                continue
            try:
                nb_pages = self.core.call_success(
                    "doc_get_nb_pages_by_url", doc_url
                )
            except Exception:
                # handled by 'paperwork_backend.chkworkdir.corrupted_page_map'
                continue
            if nb_pages is not None and nb_pages > 0:
                continue
            out_problems.append({
                "problem": "empty_doc",
                "doc_id": doc_id,
                "doc_url": doc_url,
                "human_description": {
                    "problem": _("Document %s is empty") % (doc_id,),
                    "solution": _("Delete document %s") % (doc_id,),
                },
            })

        self.core.call_all("on_progress", "chkworkdir_empty_doc", 1.0)

    def fix_work_dir(self, problems):
        total = len(problems)
        for (idx, problem) in enumerate(problems):
            if problem['problem'] != 'empty_doc':
                continue
            LOGGER.info("Fixing document %s", problem['doc_url'])
            self.core.call_all(
                "on_progress", "fixworkdir_empty_doc",
                idx / total, _("Deleting empty doc %s") % (problem['doc_id'],)
            )
            self.core.call_all("storage_delete_doc_id", problem['doc_id'])
        self.core.call_all("on_progress", "fixworkdir_empty_doc", 1.0)
