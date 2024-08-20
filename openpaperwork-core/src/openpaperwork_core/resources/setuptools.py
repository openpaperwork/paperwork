import logging
try:
    import importlib.resources
    IMPORTLIB_RESOURCES_AVAILABLE = True
except Exception:
    IMPORTLIB_RESOURCES_AVAILABLE = False

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    def get_interfaces(self):
        return ['resources']

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
        ]

    def resources_get_file(self, pkg, filename):
        if not IMPORTLIB_RESOURCES_AVAILABLE:
            LOGGER.warning("importlib.resources not available !")
            return

        path = importlib.resources.files(pkg).joinpath(filename)
        LOGGER.debug("%s:%s --> %s", pkg, filename, path)
        return importlib.resources.as_file(path)

    def resources_get_dir(self, pkg, dirname):
        return self.resources_get_file(pkg, dirname)
