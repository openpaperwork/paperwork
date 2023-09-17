"""
This plugin handles different working directories by hashing their path
and adding a part of this hash to the data directory.

If a working directly was not loaded for at least one month, it is
deleted, again.
"""
import datetime
import logging
import base64
import hashlib
import os

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

WORK_DIR_NAME = "workdir_data"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return ["data_dir_handler"]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'paths',
                'defaults': ['openpaperwork_core.paths.xdg'],
            },
            {

                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
        ]

    def init(self, core):
        super().init(core)
        self._delete_old_directories()

    def on_storage_changed(self):
        LOGGER.info(
            "Work directory has changed --> data directory has to change too"
        )
        self.core.call_all("on_data_dir_changed")

    @staticmethod
    def _hash_dir(url):
        dir_hash = hashlib.sha256(url.encode()).digest()[:6]
        encoded_hash = base64.urlsafe_b64encode(dir_hash).decode()[:8]
        return encoded_hash

    def get_dir_mtime(self, dir_url):
        mtime = 0
        file_urls = self.core.call_success(
            "fs_recurse", dir_url, dir_included=True
        )
        for file_url in file_urls:
            file_mtime = self.core.call_success("fs_get_mtime", file_url)
            if file_mtime > mtime:
                mtime = file_mtime
        return mtime

    def _delete_old_directories(self, days_to_data_dir_deletion=31):
        data_dir = self.core.call_success("paths_get_data_dir")
        work_data_dir = self.core.call_success(
            "fs_join", data_dir, WORK_DIR_NAME)
        folder_content = self.core.call_success(
            "fs_listdir", work_data_dir)
        now = datetime.datetime.now()
        for file in folder_content:
            if self.core.call_success("fs_isdir", file):
                mtime = self.get_dir_mtime(file)
                modified = datetime.datetime.fromtimestamp(mtime)
                time_diff = now - modified
                if time_diff.days >= days_to_data_dir_deletion:
                    LOGGER.info(
                        "Removing directory %s as it is older than %i days."
                        % (file, days_to_data_dir_deletion))
                    self.core.call_success("fs_rm_rf", file, trash=False)

    def data_dir_handler_get_individual_data_dir(self):
        work_dir = self.core.call_success("storage_get_id")
        data_dir = self.core.call_success("paths_get_data_dir")
        encoded_hash = Plugin._hash_dir(work_dir)
        workdir_data_folder = self.core.call_success(
            "fs_join", data_dir, WORK_DIR_NAME)
        individual_data_dir = self.core.call_success(
            "fs_join", workdir_data_folder,
            "%s_%s" % (os.path.basename(work_dir), encoded_hash)
        )
        self.core.call_success("fs_mkdir_p", individual_data_dir)
        return individual_data_dir
