import collections
import datetime
import locale
import unicodedata

from .. import (_, PluginBase)


class Plugin(PluginBase):
    MONTH_FORMATS = collections.defaultdict(
        lambda: "%B",
        oc="%b",  # Occitan
    )

    @classmethod
    def get_interfaces(cls):
        return ['i18n']

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
        self.today = datetime.date.today()
        self.yesterday = self.today - datetime.timedelta(days=1)
        self.i18n_today = _("Today")
        self.i18n_yesterday = _("Yesterday")
        self.i18n_sizes = (
            _('%3.1f bytes'),
            _('%3.1f KiB'),
            _('%3.1f MiB'),
            _('%3.1f GiB'),
            _('%3.1f TiB'),
        )

    def i18n_date_short(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        if date == self.today:
            return self.i18n_today
        elif date == self.yesterday:
            return self.i18n_yesterday
        else:
            return date.strftime("%x")

    def i18n_parse_date_short(self, txt):
        if txt == self.i18n_today:
            return self.today
        elif txt == self.i18n_yesterday:
            return self.yesterday
        else:
            try:
                return datetime.datetime.strptime(txt, "%x").date()
            except ValueError:
                return None

    def i18n_date_long_year(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        return date.strftime("%Y")

    def i18n_date_long_month(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        locale_msg = None
        if hasattr(locale, 'LC_MESSAGES'):
            locale_msg = locale.getlocale(locale.LC_MESSAGES)
        elif hasattr(locale, 'LC_ALL'):
            locale_msg = locale.getlocale(locale.LC_ALL)
        if locale_msg is None or locale_msg[0] is None:
            locale_msg = None
        else:
            locale_msg = locale_msg[0].split("_", 1)[0]
        return date.strftime(self.MONTH_FORMATS[locale_msg])

    def i18n_file_size(self, num):
        for string in self.i18n_sizes:
            if num < 1024.0:
                return string % (num)
            num /= 1024.0
        return self.i18n_sizes[-1] % (num)

    def i18n_strip_accents(self, string):
        """
        Strip all the accents from the string
        """
        return u''.join(
            (
                character for character in unicodedata.normalize('NFD', string)
                if unicodedata.category(character) != 'Mn'
            )
        )

    def i18n_sort(self, string_list):
        t = [
            (self.i18n_strip_accents(str(e).lower()), e)
            for e in string_list
        ]
        t.sort()
        return [e[1] for e in t]
