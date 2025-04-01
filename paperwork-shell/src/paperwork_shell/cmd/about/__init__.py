import rich.markdown
import rich.padding
import rich.style
import rich.text
import rich_pixels

import openpaperwork_core

from ... import _


class PaperworkLogo:
    def __init__(self, core):
        self.core = core

    def show(self, console):
        logo_ctx = self.core.call_success(
            "resources_get_file",
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


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
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

        logo = PaperworkLogo(self.core)

        markdown = f"""\
# Paperwork {self.core.call_success("app_get_version")}

> {_("Because sorting documents is a machine's job.")}
"""

        sections = {}
        self.core.call_all("authors_get", sections)
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
