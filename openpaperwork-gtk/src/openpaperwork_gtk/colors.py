try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core

from . import deps


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'gtk_colors',
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(deps.GTK)

    def gtk_entry_set_colors(self, gtk_entry, fg="black", bg="#CC3030"):
        css = """
        * {
            color: %s;
            background: %s;
        }

        * selection {
            color: white;
            background: #3b84e9;
        }
        """ % (fg, bg)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        css_context = gtk_entry.get_style_context()
        css_context.add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

    def gtk_entry_reset_colors(self, gtk_entry):
        self.gtk_entry_set_colors(
            gtk_entry, fg="@theme_text_color", bg="@theme_bg_color"
        )

    def gtk_theme_get_color(self, color_name):
        style = Gtk.StyleContext()
        return style.lookup_color("theme_bg_color")[1]
