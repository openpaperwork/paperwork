import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_gtk.interfaces.icon import Icon


class Plugin(
    openpaperwork_core.PluginBase,
    Icon,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
        ]

    def icon_get_pixbuf(self, icon_name, size_px):
        file_name = "{}_{}.png".format(icon_name, size_px)
        return self.core.call_success(
            GtkResources.gtk_load_pixbuf, "paperwork_gtk.icon.out", file_name
        )
