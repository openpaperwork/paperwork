import pycountry

import openpaperwork_core

from .. import _


LANGUAGES = {
    "English": _("English"),
    "French": _("French"),
    "German": _("German"),
}


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['i18n_lang']

    def i18n_lang_iso639_3_to_full(self, iso):
        attrs = [
            'iso639_3_code',
            'terminology',
            'alpha_3',
        ]
        for attr in attrs:
            try:
                r = pycountry.pycountry.languages.get(**{attr: iso})
                if r is None:
                    continue

                r = r.name

                if r in LANGUAGES:
                    return LANGUAGES[r]
                return r
            except (KeyError, UnicodeDecodeError):
                pass
        return iso
