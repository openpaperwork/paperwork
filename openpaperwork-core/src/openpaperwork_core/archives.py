"""
Used to archive logs, screenshots, etc.
Do not depends on 'fs' plugins (this plugin is used for logging and therefore
is critical --> has minimum dependencies).
"""

import datetime
import logging

from openpaperwork_core.interfaces.archives import AbstractArchiveHandler
from openpaperwork_core.interfaces.archives import FileArchives
from openpaperwork_core.interfaces.data_versioning import DataVersioning
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.paths import Paths
import openpaperwork_core


LOGGER = logging.getLogger(__name__)
ARCHIVE_FILE_DATE_FORMAT = "%Y%m%d_%H%M_%S"
MAX_DAYS = 31


class ArchiveHandler(AbstractArchiveHandler):
    def __init__(self, core, storage_name, storage_dir, file_extension):
        self.core = core
        self.storage_name = storage_name
        self.storage_dir = storage_dir
        self.file_extension = file_extension

    def get_new(self, name=None):
        if name is None:
            name = self.storage_name
        out_file_name = datetime.datetime.now().strftime(
            ARCHIVE_FILE_DATE_FORMAT
        )
        out_file_name += "_{}.{}".format(name, self.file_extension)
        out_file_path = self.core.call_success(
            Fs.fs_join, self.storage_dir, out_file_name
        )
        return out_file_path

    def get_archived(self):
        for f in self.core.call_success(Fs.fs_listdir, self.storage_dir):
            f = self.core.call_success(Fs.fs_basename, f)
            if not f.lower().endswith(".{}".format(self.file_extension)):
                continue
            short_f = "_".join(f.split("_", 3)[:3])
            try:
                date = datetime.datetime.strptime(
                    short_f, ARCHIVE_FILE_DATE_FORMAT
                )
            except ValueError as exc:
                LOGGER.warning(
                    "Unexpected filename: %s. Ignoring it",
                    f, exc_info=exc
                )
                continue
            yield (
                date, self.core.call_success(Fs.fs_join, self.storage_dir, f)
            )

    def delete_obsoletes(self):
        now = datetime.datetime.now()
        for (date, file_path) in self.get_archived():
            if (now - date).days <= MAX_DAYS:
                continue
            LOGGER.info("Deleting obsolete log file: %s", file_path)
            self.core.call_success(Fs.fs_unlink, file_path, trash=False)


class Plugin(
    openpaperwork_core.PluginBase,
    FileArchives,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DataVersioning,
                'defaults': ['openpaperwork_core.data_versioning'],
            },
            {
                'interface': Fs,
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': Paths,
                'defaults': ['openpaperwork_core.paths.xdg'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.storage_dirs = []
        data_dir = self.core.call_success(Paths.paths_get_data_dir)
        self.base_archive_dir = self.core.call_success(
            Fs.fs_join, data_dir, "openpaperwork"
        )

        LOGGER.info("Archiving to %s", self.base_archive_dir)

    def file_archive_get(self, storage_name, file_extension) -> AbstractArchiveHandler:
        self.core.call_success(Fs.fs_mkdir_p, self.base_archive_dir)
        storage_dir = self.core.call_success(
            Fs.fs_join, self.base_archive_dir, storage_name
        )
        self.storage_dirs.append(storage_dir)
        LOGGER.info("Archiving '%s' to %s", storage_name, storage_dir)
        self.core.call_success(Fs.fs_mkdir_p, storage_dir)
        archiver = ArchiveHandler(
            self.core, storage_name, storage_dir, file_extension
        )
        archiver.delete_obsoletes()
        return archiver
