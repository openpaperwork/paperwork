import openpaperwork_core

from openpaperwork_core.interfaces.l10n import L10n
from openpaperwork_core.interfaces.l10n import L10nInit


class Plugin(
    openpaperwork_core.PluginBase,
    L10nInit,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=L10n,
                defaults=['openpaperwork_core.l10n.python'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.core.call_all(
            L10n.l10n_load, "paperwork_gtk.l10n", "paperwork_gtk"
        )
