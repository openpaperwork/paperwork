from openpaperwork_core import (
    _,
    PluginBase
)
from openpaperwork_core.interfaces.shell import Shell


class Plugin(
    PluginBase,
    Shell,
):
    def cmd_complete_argparse(self, parser):
        parser.add_parser(
            "ping",
            help=_("Check that all required dependencies are installed")
        )

    def cmd_run(self, console, args):
        if args.command != 'ping':
            return None
        console.print("Pong")
        return True
