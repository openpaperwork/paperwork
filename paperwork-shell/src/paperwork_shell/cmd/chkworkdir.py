import rich.text

import openpaperwork_core
import openpaperwork_core.cmd.util

from .. import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'chkworkdir',
                'defaults': [
                    'paperwork_backend.chkworkdir.empty_doc',
                    'paperwork_backend.chkworkdir.label_color',
                ],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'chkworkdir', help=_("Check and fix work directory integrity")
        )
        p.add_argument(
            '--yes', '-y', required=False, default=False, action='store_true',
            help=_("Don't ask to fix things, just fix them")
        )

    @staticmethod
    def _color(color):
        color = "#%02X%02X%02X" % (
            int(color[0] * 0xFF),
            int(color[1] * 0xFF),
            int(color[2] * 0xFF),
        )
        return rich.text.Text("  ", rich.style.Style(bgcolor=color)) + " "

    def cmd_run(self, console, args):
        if args.command != 'chkworkdir':
            return None

        console.print(_("Checking work directory ..."))

        problems = []
        self.core.call_all("check_work_dir", problems)

        if len(problems) <= 0:
            console.print(_("No problem found"))
            return problems

        console.print("")
        console.print(_("%d problems found:") % len(problems))
        for problem in problems:
            problem_color = (
                ""
                if "problem_color" not in problem
                else self._color(problem['problem_color'])
            )
            solution_color = (
                ""
                if "solution_color" not in problem
                else self._color(problem['solution_color'])
            )

            console.print("[{}]".format(problem['problem']))
            console.print(
                rich.text.Text.from_ansi(_("- Problem: ")) +
                problem_color +
                rich.text.Text.from_ansi(problem['human_description']['problem'])
            )
            console.print(
                rich.text.Text.from_ansi(_("- Possible solution: ")) +
                solution_color +
                rich.text.Text.from_ansi(problem['human_description']['solution'])
            )
            console.print("")

        if not args.yes:
            msg = _(
                "Do you want to fix those problems automatically"
                " using the indicated solutions ?"
            )
            r = openpaperwork_core.cmd.util.ask_confirmation(
                console,
                msg,
                default_interactive='n',
                default_non_interactive='n',
            )
            if r != 'y':
                console.print("OK, nothing changed.")
                return problems

        console.print(_("Fixing ..."))
        self.core.call_all("fix_work_dir", problems)
        console.print(_("All fixed !"))
        console.print(_("Synchronizing with work directory ..."))

        self.core.call_all("transaction_sync_all")
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")
        console.print(_("All done !"))

        return problems
