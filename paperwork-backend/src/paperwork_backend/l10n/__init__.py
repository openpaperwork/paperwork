import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['l10n_init']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'l10n',
                'defaults': ['openpaperwork_core.l10n.python'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.core.call_all(
            "l10n_load", "paperwork_backend.l10n", "paperwork_backend"
        )
