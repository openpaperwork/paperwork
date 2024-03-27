import logging

import openpaperwork_core

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    """
    Locates (and optionally deletes) files at the root of the work directory.
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
                'interface': 'doc_pdf_import',
                'defaults': ['paperwork_backend.model.pdf'],
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
                "on_progress", "chkworkdir_file_at_workdir_root",
                idx / total, _("Checking doc %s") % (doc_id,)
            )
            isdir = self.core.call_success("fs_isdir", doc_url)
            if isdir:
                continue
            if doc_url.lower().endswith(".pdf"):
                out_problems.append({
                    "problem": "file_at_workdir_root",
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "human_description": {
                        "problem": _("Document %s is not a directory") % (
                            doc_id,
                        ),
                        "solution": _(
                            "Turn %s into <YYYYMMDD_hhmm_ss>/doc.pdf"
                        ) % (
                            doc_id,
                        ),
                    },
                    "solution": "import_pdf",
                })
            else:
                out_problems.append({
                    "problem": "file_at_workdir_root",
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "human_description": {
                        "problem": _("Document %s is not a directory") % (
                            doc_id,
                        ),
                        "solution": _("Delete document %s") % (doc_id,),
                    },
                    "solution": "delete",
                })

        self.core.call_all(
            "on_progress", "chkworkdir_file_at_workdir_root", 1.0
        )

    def fix_work_dir(self, problems):
        total = len(problems)
        for (idx, problem) in enumerate(problems):
            if problem['problem'] != 'file_at_workdir_root':
                continue
            self.core.call_all(
                "on_progress", "fixworkdir_file_at_workdir_root",
                idx / total,
                _("Fixing %s") % (problem['doc_url'],)
            )
            if problem['solution'] == "import_pdf":
                LOGGER.info("Importing %s", problem['doc_url'])
                self.core.call_success("doc_pdf_import", problem['doc_url'])
                self.core.call_success("fs_unlink", problem['doc_url'])
            else:
                LOGGER.info("Deleting %s", problem['doc_url'])
            self.core.call_all("fs_unlink", problem['doc_url'])
        self.core.call_all(
            "on_progress", "fixworkdir_file_at_workdir_root", 1.0
        )
