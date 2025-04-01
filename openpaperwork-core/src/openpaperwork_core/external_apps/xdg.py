import logging
import os
import subprocess
import shutil

from typing import Optional

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['external_apps']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
        ]

    def external_app_open_file(self, file_url):
        if shutil.which("xdg-open") is None:
            return None
        LOGGER.info("Opening %s with xdg-open", file_url)
        os.spawnlp(os.P_NOWAIT, 'xdg-open', 'xdg-open', file_url)
        return True

    def external_app_open_folder(self, folder_url):
        return self.external_app_open_file(folder_url)

    def external_app_can_send_as_attachment(self) -> bool:
        return shutil.which("xdg-email") is not None

    def external_app_send_as_attachment(self, file_url: str) -> Optional[bool]:
        if not self.external_app_can_send_as_attachment():
            return None
        LOGGER.info("Sending %s as attachment with xdg-email", file_url)
        assert file_url.startswith("file://")
        file_path = self.core.call_success("fs_unsafe", file_url)
        # xdg-email returns immediately, and we are interested in whether is
        # raises an exception
        try:
            subprocess.run(['xdg-email', '--attach', file_path], check=True)
        except subprocess.CalledProcessError as e:
            raise OSError(
                f"Failed to run xdg-email to send {file_path} as attachment"
            ) from e
        return True
