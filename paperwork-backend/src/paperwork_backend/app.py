import openpaperwork_core

from openpaperwork_core.interfaces.app import App

import paperwork_backend._version


class Plugin(
    openpaperwork_core.PluginBase,
    App,
):
    def app_get_name(self):
        return "Paperwork"

    def app_get_fs_name(self):
        return "paperwork2"

    def app_get_version(self):
        return paperwork_backend._version.version
