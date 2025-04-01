from . import PluginBase


class Plugin(PluginBase):
    """
    Plugin implementing the interface 'app' just provide some very basic
    information regarding the application we are building.
    """
    @classmethod
    def get_interfaces(cls):
        return ['app']

    def app_get_name(self):
        return "OpenPaperwork Core"

    def app_get_fs_name(self):
        return "openpaperwork_core"

    def app_get_version(self):
        return "0.0"
