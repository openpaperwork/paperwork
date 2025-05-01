import json
import logging

import openpaperwork_core

from paperwork_backend import _
from paperwork_backend.interfaces.authors import Authors


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Authors,
):
    def authors_get(self, out: dict):
        try:
            translators = json.loads(
                # Translators: put your names here. See French translation
                # for reference.
                # Must valid JSON. Must be a list of strings (your names)
                _("[]")
            )
        except json.JSONDecodeError as exc:
            LOGGER.error("Failed to load translator list", exc_info=exc)
            return
        translators = [('', translator, -1) for translator in translators]
        out['Translators'] = translators
