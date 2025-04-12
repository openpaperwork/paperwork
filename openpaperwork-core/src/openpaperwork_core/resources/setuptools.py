import logging
import os
try:
    import importlib.resources
    IMPORTLIB_RESOURCES_AVAILABLE = True
except Exception:
    IMPORTLIB_RESOURCES_AVAILABLE = False

from openpaperwork_core import PluginBase
from openpaperwork_core.interfaces.resources import Resources


LOGGER = logging.getLogger(__name__)


class Plugin(
    PluginBase,
    Resources,
):
    def resources_get_file(self, pkg, filename):
        if not IMPORTLIB_RESOURCES_AVAILABLE:
            LOGGER.warning("importlib.resources not available !")
            return

        path = importlib.resources.files(pkg).joinpath(filename)

        if not os.access(path, os.R_OK):
            LOGGER.warning(
                "Failed to find resource file %s/%s,"
                " tried at path %s.", pkg, filename, path
            )
            return None

        LOGGER.debug("%s:%s --> %s", pkg, filename, path)
        return importlib.resources.as_file(path)

    def resources_get_dir(self, pkg, dirname):
        return self.resources_get_file(pkg, dirname)
