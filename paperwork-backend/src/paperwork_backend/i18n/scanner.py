import logging
import re

from openpaperwork_core.interfaces.l10n import L10n
import openpaperwork_core

from paperwork_backend import _
from paperwork_backend.interfaces.i18n_scanner import I18nScanner


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    I18nScanner,
):
    RE_SPLIT_SOURCE_NAME = [
        re.compile(r'([()])'),
        re.compile(r'(\W)'),
    ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': L10n,
                'defaults': ['openpaperwork_core.l10n.python'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        # Need the l10n plugin to be loaded first before getting the
        # translations
        self.keywords = {
            "centrally aligned": _("centrally aligned"),
            "feeder": _("Feeder"),
            "flatbed": _("Flatbed"),
            "left aligned": _("left aligned"),
            "right aligned": _("right aligned"),
        }

    def i18n_scanner_source(self, source_name):
        original = source_name

        for regex in self.RE_SPLIT_SOURCE_NAME:
            source_name = regex.split(source_name)
            for i in range(0, len(source_name)):
                if source_name[i].lower() in self.keywords:
                    source_name[i] = self.keywords[source_name[i].lower()]
            source_name = "".join(source_name)

        LOGGER.debug("I18n: %s --> %s", original, source_name)
        return source_name
