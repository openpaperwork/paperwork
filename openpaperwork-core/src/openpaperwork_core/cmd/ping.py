from openpaperwork_core import (
    _,
    PluginBase
)


class Plugin(PluginBase):
    def __init__(self):
        self.console = None

    def get_interfaces(self):
        return ['shell']

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
