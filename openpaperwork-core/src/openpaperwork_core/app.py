from openpaperwork_core.interfaces.app import App
import openpaperwork_core


class Plugin(
    openpaperwork_core.PluginBase,
    App
):
    """
    Plugin implementing the interface 'app' just provide some very basic
    information regarding the application we are building.
    """

    def app_get_name(self):
        return "OpenPaperwork Core"

    def app_get_fs_name(self):
        return "openpaperwork_core"

    def app_get_version(self):
        return "0.0"
