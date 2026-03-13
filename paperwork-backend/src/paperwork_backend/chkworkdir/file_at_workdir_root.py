import logging

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.progress import ProgressListener
import openpaperwork_core

from paperwork_backend import _
from paperwork_backend.interfaces.chkworkdir import Chkworkdir
from paperwork_backend.interfaces.doc_pdf import DocPdf
from paperwork_backend.interfaces.doc_storage import DocStorage


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkworkdir,
):
    """
    Locates (and optionally deletes) files at the root of the work directory.
    """
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocPdf,
                defaults=['paperwork_backend.model.pdf'],
            ),
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_gtk.fs.gio"],
            ),
        ]

    def check_work_dir(self, out_problems: list):
        all_docs = []
        self.core.call_all(DocStorage.storage_get_all_docs, all_docs, only_valid=False)
        all_docs.sort()

        total = len(all_docs)
        LOGGER.info("Checking work directory (%d documents)", total)
        for (idx, (doc_id, doc_url)) in enumerate(all_docs):
            self.core.call_all(
                ProgressListener.on_progress, "chkworkdir_file_at_workdir_root",
                idx / total, _("Checking doc %s") % (doc_id,)
            )
            isdir = self.core.call_success(Fs.fs_isdir, doc_url)
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
            ProgressListener.on_progress, "chkworkdir_file_at_workdir_root", 1.0
        )

    def fix_work_dir(self, problems):
        total = len(problems)
        for (idx, problem) in enumerate(problems):
            if problem['problem'] != 'file_at_workdir_root':
                continue
            self.core.call_all(
                ProgressListener.on_progress, "fixworkdir_file_at_workdir_root",
                idx / total,
                _("Fixing %s") % (problem['doc_url'],)
            )
            if problem['solution'] == "import_pdf":
                LOGGER.info("Importing %s", problem['doc_url'])
                self.core.call_success(DocPdf.doc_pdf_import, problem['doc_url'])
                self.core.call_success(Fs.fs_unlink, problem['doc_url'])
            else:
                LOGGER.info("Deleting %s", problem['doc_url'])
            self.core.call_all(Fs.fs_unlink, problem['doc_url'])
        self.core.call_all(
            ProgressListener.on_progress, "fixworkdir_file_at_workdir_root", 1.0
        )
