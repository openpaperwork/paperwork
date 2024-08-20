import random

import fabulous.image
import fabulous.text

import rich.text

import openpaperwork_core

from ... import _


# XXX(Jflesch): crappy workaround for an unmaintained library ...
fabulous.image.basestring = str


VALIDATED_FONTS = """
comic
Comic_Sans_MS
Comic_Sans_MS_Bold
comicbd
LiberationMono-Bold
LiberationSans-Bold
times
timesbd
FreeMono
FreeMonoBold
FreeMonoBoldOblique
FreeMonoOblique
FreeSans
FreeSansBold
FreeSansBoldOblique
FreeSansOblique
FreeSerif
FreeSerifBold
FreeSerifBoldItalic
FreeSerifItalic
""".strip().split()  # to make copy and paste faster

COLORS = [
    '#0099ff',
    '#ff4400',
    '#00bd22',
    '#bf00ff',
]


class Paperwork(object):
    def __init__(self, core, fonts):
        self.core = core
        self.fonts = fonts

    def show(self, console):
        nb_lines = 0

        logo_ctx = self.core.call_success(
            "resources_get_file",
            "paperwork_shell.cmd.about", "logo.png"
        )
        with logo_ctx as logo:
            logo = fabulous.image.Image(logo, width=60)
        logo = logo.reduce(logo.convert())
        for line in logo:
            console.print(rich.text.Text.from_ansi((16 * " ") + line))
            nb_lines += 1

        font = "FreeSans"
        if font not in self.fonts:
            font = self.fonts[0]

        txt = fabulous.text.Text(
            "Paperwork",
            skew=5, color="#abcdef", font=font, fsize=25, shadow=False
        )
        for line in txt:
            console.print(rich.text.Text.from_ansi(line))
            nb_lines += 1

        console.print("Paperwork")
        console.print(
            (8 * " ")
            + _('Version: ') + self.core.call_success("app_get_version")
        )
        console.print(
            (8 * " ")
            + _("Because sorting documents is a machine's job.")
        )
        nb_lines += 3
        return nb_lines


class Section(object):
    def __init__(self, name, authors, fonts):
        self.name = name
        self.authors = authors
        self.fonts = fonts

    @staticmethod
    def _group_small_words(words):
        buf = []
        for word in words:
            buf.append(word)
            if len(word) > 3:
                yield " ".join(buf)
                buf = []
        if len(buf) > 0:
            yield " ".join(buf)

    def show(self, console):
        nb_lines = 0
        color = random.choice(COLORS)
        font = random.choice(self.fonts)

        words = self.name.split()
        for word in self._group_small_words(words):
            txt = fabulous.text.Text(
                word, skew=0, color=color, font=font, fsize=18, shadow=False
            )
            for line in txt:
                console.print(rich.text.Text.from_ansi(line))
                nb_lines += 1

        console.print(self.name)
        nb_lines += 1
        for author in self.authors:
            txt = author[1]
            if author[2] > 0:
                txt += " ({})".format(author[2])
            console.print((8 * " ") + txt)
            nb_lines += 1

        return nb_lines


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                'interface': 'app',
                'defaults': ['paperwork_backend.app'],
            },
            {
                'interface': 'authors',
                'defaults': ['paperwork_backend.authors'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        parser.add_parser('about', help=_("About Paperwork"))

    def cmd_run(self, console, args):
        if args.command != 'about':
            return None

        fonts = self._get_available_fonts()

        sections = {}
        self.core.call_all("authors_get", sections)
        sections = [x for x in sections.items()]
        sections.sort(key=lambda x: x[0].lower())

        sections = (
            [Paperwork(self.core, fonts)] +
            [Section(k, v, fonts) for (k, v) in sections if len(v) >= 0]
        )

        for section in sections:
            section.show(console)
            if section != sections[-1]:
                for x in range(0, 7):
                    console.print("")
        console.print("")
        console.print("")

    def _get_available_fonts(self):
        all_fonts = fabulous.text.get_font_files()
        all_fonts = {n for n in all_fonts.keys()}

        out = []
        for font in VALIDATED_FONTS:
            if font not in all_fonts:
                continue
            out.append(font)
        return out
