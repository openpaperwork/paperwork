import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_about',
            'gtk_window_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'authors',
                'defaults': ['paperwork_backend.authors'],
            },
            {
                'interface': 'app',
                'defaults': ['paperwork_backend.app'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'icon',
                'defaults': ['paperwork_gtk.icon'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.windows = []

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _set_authors_str(self, method, authors):
        out = ""
        for (email, name, line_count) in authors:
            if line_count > 0:
                out += "{} ({})\n".format(name, line_count)
            else:
                out += "{}\n".format(name)
        method(out)

    def _set_authors_list(self, method, authors):
        out = []
        for (email, name, line_count) in authors:
            txt = name
            if line_count > 0:
                txt += " ({})".format(line_count)
            out.append(txt)
        method(out)

    def _on_close(self, dialog, *args, **kwargs):
        LOGGER.info("Closing dialog 'about'")
        dialog.destroy()
        self.core.call_all("on_gtk_window_closed", dialog)

    def gtk_open_about(self):
        LOGGER.info("Opening dialog 'about'")
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.about", "about.glade"
        )

        authors = {}
        self.core.call_all("authors_get", authors)

        documentation = authors.pop("Documentation", [])
        translators = authors.pop("Translators", [])
        version = self.core.call_success("app_get_version")
        icon = self.core.call_success("icon_get_pixbuf", "paperwork", 128)

        about_dialog = widget_tree.get_object("about_dialog")
        about_dialog.set_logo(icon)
        about_dialog.set_version(version)

        for (k, v) in authors.items():
            self._set_authors_list(
                lambda authors: about_dialog.add_credit_section(k, authors),
                v
            )
        if len(translators) > 0:
            self._set_authors_str(
                about_dialog.set_translator_credits, translators
            )
        self._set_authors_list(about_dialog.set_documenters, documentation)

        about_dialog.set_transient_for(self.windows[-1])
        about_dialog.set_visible(True)

        about_dialog.connect("close", self._on_close)
        about_dialog.connect("response", self._on_close)

        self.core.call_all("on_gtk_window_opened", about_dialog)
