import ctypes
import gettext
import locale
import logging
import os
import sys

from openpaperwork_core import PluginBase
from openpaperwork_core.interfaces.frozen import Frozen
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.l10n import L10n
from openpaperwork_core.interfaces.resources import Resources


LOGGER = logging.getLogger(__name__)


class Plugin(
    PluginBase,
    L10n,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                # if frozen, we need sys._MEIPASS to be set correctly
                'interface': Frozen,
                'defaults': ['openpaperwork_core.frozen'],
            },
            {
                'interface': Fs,
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': Resources,
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.libintl = None

        if os.name == "nt" and os.getenv('LANG') is None:
            (lang, enc) = locale.getdefaultlocale()
            os.environ['LANG'] = lang

        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error:
            # happens, for instance when LC_ALL is set to a nonexisting locale
            LOGGER.warning(
                "Failed to set localization. Localization will be disabled"
            )
            return

        self.libintl = None
        if getattr(sys, 'frozen', False):
            libintl_path = os.path.abspath(os.path.join(
                sys._MEIPASS, "libintl-8.dll"
            ))
            if not os.path.exists(libintl_path):
                LOGGER.warning("Failed to find library libintl-8.dll")
            else:
                self.libintl = ctypes.cdll.LoadLibrary(libintl_path)

        self.l10n_load('openpaperwork_core.l10n', 'openpaperwork_core')

    def l10n_load(self, python_package, text_domain):
        path_ctx = self.core.call_success(
            Resources.resources_get_dir, python_package, 'out'
        )
        with path_ctx as path:
            if path is None:
                LOGGER.error(
                    "Failed to access ressources '%s/out'", python_package
                )
                return None

            path = str(path)

            mo_file = gettext.find(text_domain, path)
            if mo_file is None:
                # expected if we don't have translation for the user language
                LOGGER.info(
                    "Failed to find valid locale for '%s' (path=%s)",
                    text_domain, path
                )
                # we still try to keep going

            LOGGER.info("Binding text domain %s to '%s'", text_domain, path)

            if self.libintl is not None:
                self.libintl.bindtextdomain(text_domain, path)
                self.libintl.bind_textdomain_codeset(text_domain, 'UTF-8')

            for module in (gettext, locale):
                if hasattr(module, 'bindtextdomain'):
                    module.bindtextdomain(text_domain, path)
                if hasattr(module, 'textdomain'):
                    module.textdomain(text_domain)
