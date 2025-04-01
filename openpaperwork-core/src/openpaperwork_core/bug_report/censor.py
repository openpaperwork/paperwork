import logging

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    """
    Censor bug report attachments
    """
    PRIORITY = -10000

    @classmethod
    def get_interfaces(cls):
        return ['bug_report_attachments']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'censor',
                'defaults': ['openpaperwork_core.censor'],
            },
        ]

    def _censor_attachment(self, attachment_id, args):
        url = self.core.call_success(
            "bug_report_get_attachment_file_url", attachment_id, *args
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

        basename = self.core.call_success("fs_basename", url)
        if basename.startswith("censored_"):
            LOGGER.info("Attachmnent %s appears to be already censored", url)
            return

        LOGGER.info("Censoring %s:%s", attachment_id, url)

        censored = self.core.call_success(
            "censor_txt_file", url, tmp_on_disk=True
        )
        self.core.call_all(
            "bug_report_update_attachment", attachment_id, {
                "censored": True,
                "file_url": censored,
            }, *args
        )

    def on_bug_report_attachment_selected(self, attachment_id, *args):
        self._censor_attachment(attachment_id, args)

    def bug_report_update_attachment(self, attachment_id, infos: dict, *args):
        if 'censored' in infos:
            return
        self._censor_attachment(attachment_id, args)
