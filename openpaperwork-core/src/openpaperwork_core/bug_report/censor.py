import logging

from openpaperwork_core.interfaces.bug_report_attachment import BugReportAttachmentFileUrl
from openpaperwork_core.interfaces.bug_report_attachment import BugReportAttachmentUpdate
from openpaperwork_core.interfaces.bug_report_attachment import BugReportAttachmentSelectionListener
from openpaperwork_core.interfaces.censor import Censor
from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    BugReportAttachmentUpdate,
    BugReportAttachmentSelectionListener,
):
    """
    Censor bug report attachments
    """
    PRIORITY = -10000

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=BugReportAttachmentFileUrl,
                defaults=["openpaperwork_gtk.bug_report"],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=Censor,
                defaults=['openpaperwork_core.censor'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_core.fs.python"],
            ),
        ]

    def _censor_attachment(self, attachment_id, args):
        url = self.core.call_success(
            BugReportAttachmentFileUrl.bug_report_get_attachment_file_url,
            attachment_id, *args
        )
        if url is None:
            LOGGER.info(
                "Attachment %s has no URL yet. Can't censor", attachment_id
            )
            return

        if not url.endswith(".conf") and not url.endswith(".txt"):
            LOGGER.info(
                    "Unknown file type: %s:%s. Can't censor",
                    attachment_id, url
            )
            return

        basename = self.core.call_success(Fs.fs_basename, url)
        if basename.startswith("censored_"):
            LOGGER.info("Attachmnent %s appears to be already censored", url)
            return

        LOGGER.info("Censoring %s:%s", attachment_id, url)

        censored = self.core.call_success(
            Censor.censor_txt_file, url, tmp_on_disk=True
        )
        self.core.call_all(
            BugReportAttachmentUpdate.bug_report_update_attachment, attachment_id, {
                "censored": True,
                "file_url": censored,
            }, *args
        )

    def on_bug_report_attachment_selected(self, attachment_id, *args):
        self._censor_attachment(attachment_id, args)

    @openpaperwork_core.noop
    def on_bug_report_attachment_unselected(self, attachment_id, *args):
        pass

    def bug_report_update_attachment(self, attachment_id, infos: dict, *args):
        if 'censored' in infos:
            return
        self._censor_attachment(attachment_id, args)
