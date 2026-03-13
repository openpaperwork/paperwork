import os

import openpaperwork_core
from openpaperwork_core.interfaces.app import App
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.paths import Paths


class Plugin(
    openpaperwork_core.PluginBase,
    Paths,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=App,
                defaults=['openpaperwork_core.app'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_core.fs.python']
            ),
        ]

    def paths_get_config_dir(self):
        config_dir = self.core.call_success(
            Fs.fs_safe,
            os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        )
        self.core.call_success(Fs.fs_mkdir_p, config_dir)

        if os.name == 'nt':  # hide ~/.local on Windows
            self.core.call_success(Fs.fs_hide, config_dir)

        return config_dir

    def paths_get_data_dir(self):
        local_dir = os.path.expanduser("~/.local")
        data_dir = os.getenv("XDG_DATA_HOME", os.path.join(local_dir, "share"))

        data_dir = self.core.call_success(Fs.fs_safe, data_dir)

        app_name = self.core.call_success(App.app_get_fs_name)
        app_dir = self.core.call_success(Fs.fs_join, data_dir, app_name)
        self.core.call_success(Fs.fs_mkdir_p, app_dir)

        if os.name == 'nt':  # hide ~/.local on Windows
            local_dir = self.core.call_success(Fs.fs_safe, local_dir)
            if self.core.call_success(Fs.fs_isdir, local_dir) is not None:
                self.core.call_success(Fs.fs_hide, local_dir)

        return app_dir
