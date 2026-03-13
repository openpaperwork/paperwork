import logging

from openpaperwork_core.interfaces.data_versioning import DataVersioning
from openpaperwork_core.interfaces.data_versioning import DataVersioningListener
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.paths import Paths
import openpaperwork_core


LOGGER = logging.getLogger(__name__)

# TODO(Jflesch): this version shouldn't be common to all applications using
# Openpaperwork-core
DATA_VERSION = 2


class Plugin(
    openpaperwork_core.PluginBase,
    DataVersioning,
):
    """
    Keep a version number in ~/.local/share/paperwork2/data_version.
    If the version doesn't match 'DATA_VERSION', right before syncing,
    delete ~/.local/share/paperwork2 to force a full synchronisation.
    """

    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DataVersioningListener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_core.fs.python'],
            ),
            openpaperwork_core.Dependency(
                interface=Paths,
                defaults=['openpaperwork_core.paths.xdg'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        data_dir = self.core.call_success(Paths.paths_get_data_dir)
        data_ver_file = self.core.call_success(
            Fs.fs_join, data_dir, "data_version"
        )

        data_version = -1
        if self.core.call_success(Fs.fs_exists, data_ver_file):
            with self.core.call_success(Fs.fs_open, data_ver_file, 'r') as fd:
                data_version = int(fd.read().strip())

        LOGGER.info(
            "Expected data version: %d ; Current data version: %d",
            DATA_VERSION, data_version
        )

        if data_version != DATA_VERSION:
            LOGGER.warning(
                "Data version doesn't match (%d != %d). Forcing full sync",
                data_version, DATA_VERSION
            )

            self.core.call_success(Fs.fs_rm_rf, data_dir, trash=False)
            # call 'paths_get_data_dir' again to recreate the data directory
            data_dir = self.core.call_success(Paths.paths_get_data_dir)

            with self.core.call_success(Fs.fs_open, data_ver_file, 'w') as fd:
                fd.write(str(DATA_VERSION))

            self.core.call_all(DataVersioningListener.on_data_files_deleted)
