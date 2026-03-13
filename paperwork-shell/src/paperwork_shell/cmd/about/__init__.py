import rich.markdown
import rich.padding
import rich.style
import rich.text
import rich_pixels

from openpaperwork_core.interfaces.app import App
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.resources import Resources
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.authors import Authors

from paperwork_shell import _


class PaperworkLogo:
    def __init__(self, core):
        self.core = core

    def show(self, console):
        logo_ctx = self.core.call_success(
            Resources.resources_get_file,
            "paperwork_shell.cmd.about", "logo.png"
        )
        with logo_ctx as logo:
            logo = rich_pixels.Pixels.from_image_path(logo, resize=(60, 60))
        logo = rich.padding.Padding(logo, (0, 16))
        console.print(logo)

        # Generated with `pyfiglet -f ansi_shadow Paperwork`.
        txt = """
        ██████╗  █████╗ ██████╗ ███████╗██████╗ ██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗
        ██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝
        ██████╔╝███████║██████╔╝█████╗  ██████╔╝██║ █╗ ██║██║   ██║██████╔╝█████╔╝
        ██╔═══╝ ██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗██║███╗██║██║   ██║██╔══██╗██╔═██╗
        ██║     ██║  ██║██║     ███████╗██║  ██║╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗
        ╚═╝     ╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
        """
        for line in txt.splitlines():
            console.print(rich.text.Text(line, style=rich.style.Style(color='#abcdef')))


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=App,
                defaults=['paperwork_backend.app'],
            ),
            openpaperwork_core.Dependency(
                interface=Authors,
                defaults=['paperwork_backend.authors'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_core.fs.python'],
            ),
            openpaperwork_core.Dependency(
                interface=Resources,
                defaults=['openpaperwork_core.resources.setuptools'],
            ),
        ]

    def cmd_complete_argparse(self, parser):
        parser.add_parser('about', help=_("About Paperwork"))

    def cmd_run(self, console, args):
        if args.command != 'about':
            return None

        logo = PaperworkLogo(self.core)

        markdown = f"""\
# Paperwork {self.core.call_success(App.app_get_version)}

> {_("Because sorting documents is a machine's job.")}
"""

        sections = {}
        self.core.call_all(Authors.authors_get, sections)
        for name, authors in sorted(sections.items(), key=lambda x: x[0].lower()):
            markdown += f"## {name}\n"
            for author in authors:
                txt = author[1]
                if author[2] > 0:
                    txt = f"{txt} ({author[2]})"
                markdown += f"- {txt}\n"
        md = rich.markdown.Markdown(markdown)

        logo.show(console)
        console.print(md)
