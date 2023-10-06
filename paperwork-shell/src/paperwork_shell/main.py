import argparse
import json
import sys
import traceback

import rich.console
import rich.text

import openpaperwork_core
import openpaperwork_core.cmd

import paperwork_backend


# this import must be non-relative due to cx_freeze running this .py
# as an independant Python script
from paperwork_shell import _


DEFAULT_SHELL_PLUGINS = paperwork_backend.DEFAULT_PLUGINS + [
    "paperwork_backend.guesswork.cropping.libpillowfight",
    "paperwork_shell.cmd.chkworkdir",
    "paperwork_shell.cmd.delete",
    "paperwork_shell.cmd.edit",
    "paperwork_shell.cmd.export",
    "paperwork_shell.cmd.extra_text",
    "paperwork_shell.cmd.import",
    "paperwork_shell.cmd.label",
    "paperwork_shell.cmd.move",
    "paperwork_shell.cmd.ocr",
    "paperwork_shell.cmd.rename",
    "paperwork_shell.cmd.reset",
    "paperwork_shell.cmd.scan",
    "paperwork_shell.cmd.scanner",
    "paperwork_shell.cmd.search",
    "paperwork_shell.cmd.show",
    "paperwork_shell.cmd.sync",
    "paperwork_shell.display.docrendering.extra_text",
    "paperwork_shell.display.docrendering.img",
    "paperwork_shell.display.docrendering.labels",
    "paperwork_shell.display.docrendering.text",
    "paperwork_shell.l10n",
    "paperwork_shell.logs.print",
]

DEFAULT_CLI_PLUGINS = DEFAULT_SHELL_PLUGINS + [
    "paperwork_shell.cmd.about",
    "paperwork_shell.display.progress",
    "paperwork_shell.display.rich",
    "paperwork_shell.display.scan",
]
DEFAULT_JSON_PLUGINS = DEFAULT_SHELL_PLUGINS


class RichConsole:
    def __init__(self):
        self.console = rich.console.Console()

    def print(self, line):
        if isinstance(line, str):
            line = rich.text.Text(line)
        self.console.print(line)

    def input(self, prompt=""):
        return self.console.input(rich.text.Text(prompt + "\n"))


def main_main(in_args, application_name, default_plugins, interactive):
    # To load the plugins, we need first to load the configuration plugin
    # to get the list of plugins to load.
    # The configuration plugin may write traces using logging, so we better
    # enable and configure the plugin logs.print first.

    core = openpaperwork_core.Core()
    # plugin 'uncaught_exceptions' requires a mainloop plugin
    core.load('openpaperwork_core.mainloop.asyncio')
    core.load('paperwork_shell.logs.print')
    for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
        core.load(module_name)
    core.init()

    core.call_all("config_load")
    core.call_all("config_load_plugins", application_name, default_plugins)

    core.call_all("init_logs", application_name, "warning")

    parser = argparse.ArgumentParser()
    cmd_parser = parser.add_subparsers(
        help=_('command'), dest='command', required=True
    )

    core.call_all("cmd_complete_argparse", cmd_parser)
    args = parser.parse_args(in_args)

    if interactive:
        console = RichConsole()
    else:
        console = openpaperwork_core.cmd.DummyConsole()

    core.call_all("cmd_set_console", console)
    if interactive:
        r = core.call_all("cmd_run", console=console, args=args)
    else:
        r = core.call_success("cmd_run", console=console, args=args)

    core.call_all("on_quit")
    return r


def json_main():
    try:
        r = main_main(
            sys.argv[1:], 'paperwork-json', DEFAULT_JSON_PLUGINS,
            interactive=False
        )
        print(json.dumps(
            r,
            indent=4,
            separators=(',', ': '),
            sort_keys=True
        ))
    except Exception as exc:
        stack = traceback.format_exc().splitlines()
        print(json.dumps(
            {
                "status": "error",
                "exception": str(type(exc)),
                "args": str(exc.args),
                "reason": str(exc),
                "stack": stack,
            },
            indent=4,
            separators=(',', ': '),
            sort_keys=True
        ))
        sys.exit(2)


def cli_main():
    main_main(
        sys.argv[1:], 'paperwork-cli', DEFAULT_CLI_PLUGINS, interactive=True
    )


if __name__ == "__main__":
    # Do not remove. Cx_freeze goes throught here
    if "paperwork-json" in sys.argv[0]:
        json_main()
    else:
        cli_main()
