import logging

from openpaperwork_core.interfaces.config import Config
import openpaperwork_core

import openpaperwork_core.deps
from openpaperwork_gtk.interfaces.gtk import GtkResources  # noqa: E402
from paperwork_backend.interfaces.i18n_lang import I18nLang
from paperwork_backend.interfaces.ocr import OcrSettings
from paperwork_gtk.interfaces.settings import GtkSettingsOcr


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase, GtkSettingsOcr):
    PRIORITY = -500

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': I18nLang,
                'defaults': ['paperwork_backend.i18n.pycountry'],
            },
            {
                'interface': OcrSettings,
                'defaults': ['paperwork_backend.pyocr'],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def complete_ocr_settings(self, parent_widget_tree):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.settings.ocr", "selector_popover.glade"
        )

        active_langs = set(self.core.call_success(OcrSettings.ocr_get_active_langs))
        LOGGER.info("Looking for available OCR languages ...")
        all_langs = self.core.call_success(OcrSettings.ocr_get_available_langs)
        LOGGER.info("Found %d languages. Translating ...", len(all_langs))
        all_langs = [
            (
                lang,
                self.core.call_success(
                    I18nLang.i18n_lang_iso639_3_to_full, lang
                )
            )
            for lang in all_langs
            # Skip Tesseract data file for page orientation guessing
            if lang != 'osd'
        ]
        all_langs.sort(key=lambda lang: lang[1])

        LOGGER.info("OCR languages: %s", all_langs)
        LOGGER.info("Active OCR languages: %s", active_langs)

        box_parent = widget_tree.get_object("ocr_selector_box")

        for lang in all_langs:
            w_tree = self.core.call_success(
                GtkResources.gtk_load_widget_tree,
                "paperwork_gtk.settings.ocr", "selector_popover_box.glade"
            )
            check = w_tree.get_object("ocr_selector_box")
            check.set_label(lang[1])
            check.set_active(lang[0] in active_langs)
            check.connect('toggled', self._on_toggle, lang[0])
            box_parent.pack_start(check, expand=False, fill=True, padding=0)
        LOGGER.info("OCR selector ready")

        popover = widget_tree.get_object("ocr_selector")
        parent_widget_tree.get_object("ocr_langs").set_popover(popover)

    def _on_toggle(self, checkbox, lang):
        active_langs = self.core.call_success(OcrSettings.ocr_get_active_langs)
        lang_enabled = lang in active_langs
        LOGGER.info("Language toggled: {} ({} -> {})".format(
            lang, lang_enabled, not lang_enabled
        ))
        if lang_enabled:
            active_langs.remove(lang)
        else:
            active_langs.append(lang)
        self.core.call_all(OcrSettings.ocr_set_active_langs, active_langs)
