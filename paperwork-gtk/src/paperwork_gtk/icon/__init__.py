import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['icon']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def icon_get_pixbuf(self, icon_name, size_px):
        file_name = "{}_{}.png".format(icon_name, size_px)
        return self.core.call_success(
            "gtk_load_pixbuf", "paperwork_gtk.icon.out", file_name
        )
