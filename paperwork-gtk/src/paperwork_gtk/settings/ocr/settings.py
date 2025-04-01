import logging

import openpaperwork_core
import openpaperwork_core.deps

from ... import _

LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -500

    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_settings',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'i18n_lang',
                'defaults': ['paperwork_backend.i18n.pycountry'],
            },
            {
                'interface': 'ocr_settings',
                'defaults': ['paperwork_backend.pyocr'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings.ocr",
            "settings.glade"
        )

        label = widget_tree.get_object("ocr_langs_label")
        self._update_langs(label)

        self.core.call_all("complete_ocr_settings", widget_tree)

        def refresh(*args, **kwargs):
            self._update_langs(label)

        def disable_refresh(*args, **kwargs):
            self.core.call_all("config_remove_observer", "ocr_langs", refresh)

        self.core.call_all("config_add_observer", "ocr_langs", refresh)

        global_widget_tree.get_object("settings_window").connect(
            "destroy", disable_refresh
        )

        self.core.call_success(
            "add_setting_to_dialog", global_widget_tree,
            _("Optical Character Recognition"),
            [widget_tree.get_object("ocr_langs")]
        )

    def _update_langs(self, label):
        langs = self.core.call_success("ocr_get_active_langs")
        langs = [
            self.core.call_success("i18n_lang_iso639_3_to_full", lang)
            for lang in langs
        ]
        langs = ", ".join(langs)
        if langs == "":
            langs = _("OCR disabled")
        LOGGER.info("OCR languages: %s", langs)
        label.set_text(langs)
