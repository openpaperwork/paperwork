import logging
import os

import openpaperwork_core
from openpaperwork_core.interfaces.flatpak import Flatpak

from openpaperwork_gtk.interfaces.gtk import GtkInit


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase, GtkInit):
    PRIORITY = 10000

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Flatpak,
                'defaults': ['openpaperwork_core.flatpak'],
            },
        ]

    def gtk_init(self, *args, **kwargs):
        # Flatpak workaround: make sure the fonts will be rendered correctly in
        # PDF files. Otherwise, sometime we get a weird error in the console:
        # "some font thing has failed" and no text is rendered when rendering
        # PDF pages.
        if self.core.call_success(Flatpak.is_in_flatpak):
            LOGGER.info("Running `fc-cache -f` ...")
            r = os.system("fc-cache -f")
            r = os.waitstatus_to_exitcode(r)
            if r == 0:
                LOGGER.info("`fc-cache -f` has succeded")
            else:
                LOGGER.warning("`fc-cache -f` has failed: r=%d", r)
