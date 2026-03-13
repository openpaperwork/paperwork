import logging

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.progress import ProgressListener
import openpaperwork_core

from paperwork_backend import _
from paperwork_backend.interfaces.chkworkdir import Chkworkdir
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import Docs


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkworkdir,
):
    """
    Locates (and optionally deletes) empty directories in the work
    directory.
    """
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=Docs,
                defaults=['paperwork_backend.model'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_core.fs.python'],
            ),
            openpaperwork_core.Dependency(
                interface=ProgressListener,
                defaults=[],
                optional=True,
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
                ProgressListener.on_progress, "chkworkdir_empty_doc",
                idx / total, _("Checking doc %s") % (doc_id,)
            )
            isdir = self.core.call_success(Fs.fs_isdir, doc_url)
            if not isdir:
                LOGGER.debug("Document %s is not a directory", doc_url)
                continue
            try:
                nb_pages = self.core.call_success(
                    Docs.doc_get_nb_pages_by_url, doc_url
                )
            except Exception as exc:
                # handled by 'paperwork_backend.chkworkdir.corrupted_page_map'
                LOGGER.debug("Document %s: %s", doc_url, repr(exc), exc_info=exc)
                continue
            LOGGER.debug("Document %s: %s pages", doc_url, nb_pages)
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

        self.core.call_all(ProgressListener.on_progress, "chkworkdir_empty_doc", 1.0)

    def fix_work_dir(self, problems):
        total = len(problems)
        for (idx, problem) in enumerate(problems):
            if problem['problem'] != 'empty_doc':
                continue
            LOGGER.info("Fixing document %s", problem['doc_url'])
            self.core.call_all(
                ProgressListener.on_progress, "fixworkdir_empty_doc",
                idx / total, _("Deleting empty doc %s") % (problem['doc_id'],)
            )
            self.core.call_all(DocStorage.storage_delete_doc_id, problem['doc_id'])
        self.core.call_all(ProgressListener.on_progress, "fixworkdir_empty_doc", 1.0)
