import os

from .. import PluginBase


class Plugin(PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['paths']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app',
                'defaults': ['openpaperwork_core.app'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python']
            },
        ]

    def paths_get_config_dir(self):
        config_dir = self.core.call_success(
            "fs_safe",
            os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        )
        self.core.call_success("fs_mkdir_p", config_dir)

        if os.name == 'nt':  # hide ~/.local on Windows
            self.core.call_success("fs_hide", config_dir)

        return config_dir

    def paths_get_data_dir(self):
        local_dir = os.path.expanduser("~/.local")
        data_dir = os.getenv("XDG_DATA_HOME", os.path.join(local_dir, "share"))

        data_dir = self.core.call_success("fs_safe", data_dir)

        app_name = self.core.call_success("app_get_fs_name")
        app_dir = self.core.call_success("fs_join", data_dir, app_name)
        self.core.call_success("fs_mkdir_p", app_dir)

        if os.name == 'nt':  # hide ~/.local on Windows
            local_dir = self.core.call_success("fs_safe", local_dir)
            if self.core.call_success("fs_isdir", local_dir) is not None:
                self.core.call_success("fs_hide", local_dir)

        return app_dir
