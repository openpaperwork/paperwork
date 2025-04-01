import getpass
import logging
import os
import socket
import urllib.parse

from . import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['censor']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.replacements = (
            (os.path.expanduser("~"), "###HOME_DIR###"),
            (urllib.parse.quote(os.path.expanduser("~")), "###HOME_DIR###"),
            (getpass.getuser(), "###USER_NAME###"),
            (urllib.parse.quote(getpass.getuser()), "###USER_NAME###"),
            (socket.gethostname(), "###HOST_NAME###"),
            (urllib.parse.quote(socket.gethostname()), "###HOST_NAME###"),
        )

    def censor_string(self, string):
        """
        Rewrite a string by censoring anything close to personal information
        (username, home directory path, host name, ...).
        """
        for r in self.replacements:
            string = string.replace(*r)
        return string

    def censor_txt_file(
            self, input_url, output_url=None, tmp_on_disk=False):
        """
        Rewrite a file but censor anything close to personal information
        (username, home directory path, host name, ...).

        Arguments:
        - file_input_url: file to censor
        - file_output_url: output file. If None, a temporary file will be
          created
        - tmp_on_disk: only used if file_output_url is None. If true,
          the temporary file will be written on disk. If false, we may
          return a memory:// URI (won't work outside of Paperwork).

        Returns:
          censored file URL
        """
        if output_url is not None:
            fd_out = self.core.call_success("fs_open", output_url, 'w')
        else:
            basename = self.core.call_success("fs_basename", input_url)
            (output_url, fd_out) = self.core.call_success(
                "fs_mktemp", prefix="censored_", suffix="_" + basename,
                mode="w", on_disk=tmp_on_disk
            )

        with fd_out:
            with self.core.call_success("fs_open", input_url, 'r') as fd_in:
                while True:
                    line = fd_in.readline()
                    if line == '':
                        break
                    line = self.censor_string(line)
                    fd_out.write(line)

        return output_url
