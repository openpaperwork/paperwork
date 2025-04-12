from openpaperwork_core.interfaces.l10n import L10n
from openpaperwork_core.interfaces.l10n import L10nInit
import openpaperwork_core


class Plugin(
    openpaperwork_core.PluginBase,
    L10nInit,
):
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
        self.core.call_all(
            L10n.l10n_load, "openpaperwork_gtk.l10n", "openpaperwork_gtk"
        )
