import logging

import openpaperwork_core
import openpaperwork_core.deps
from openpaperwork_core.interfaces.config import Config
from openpaperwork_gtk.interfaces.gtk import GtkResources
from paperwork_backend.interfaces.i18n_lang import I18nLang
from paperwork_backend.interfaces.ocr import OcrSettings

from paperwork_gtk import _
from paperwork_gtk.interfaces.settings import GtkSettingsOcr
from paperwork_gtk.interfaces.settings_dialog import SettingsDialog
from paperwork_gtk.interfaces.settings_dialog import SettingsDialogComponent

LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    SettingsDialogComponent
):
    PRIORITY = -500

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
            {
                "interface": GtkSettingsOcr,
                "defaults": ["paperwork_gtk.settings.ocr.selector_popover"],
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
            {
                'interface': SettingsDialog,
                'defaults': ['paperwork_gtk.settings'],
            },
        ]

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree, "paperwork_gtk.settings.ocr",
            "settings.glade"
        )

        label = widget_tree.get_object("ocr_langs_label")
        self._update_langs(label)

        self.core.call_all(GtkSettingsOcr.complete_ocr_settings, widget_tree)

        def refresh(*args, **kwargs):
            self._update_langs(label)

        def disable_refresh(*args, **kwargs):
            self.core.call_all(Config.config_remove_observer, "ocr_langs", refresh)

        self.core.call_all(Config.config_add_observer, "ocr_langs", refresh)

        global_widget_tree.get_object("settings_window").connect(
            "destroy", disable_refresh
        )

        self.core.call_success(
            SettingsDialog.add_setting_to_dialog, global_widget_tree,
            _("Optical Character Recognition"),
            [widget_tree.get_object("ocr_langs")]
        )

    def _update_langs(self, label):
        langs = self.core.call_success(OcrSettings.ocr_get_active_langs)
        langs = [
            self.core.call_success(I18nLang.i18n_lang_iso639_3_to_full, lang)
            for lang in langs
        ]
        langs = ", ".join(langs)
        if langs == "":
            langs = _("OCR disabled")
        LOGGER.info("OCR languages: %s", langs)
        label.set_text(langs)

    @openpaperwork_core.noop
    def on_settings_closed(self, settings_dialog_widget_tree):
        pass
