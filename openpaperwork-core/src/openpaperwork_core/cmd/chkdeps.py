import collections
import distro
import logging
import os
import sys

from openpaperwork_core.cmd import util
from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.shell import Shell
from openpaperwork_core import _
import openpaperwork_core


LOGGER = logging.getLogger(__name__)


PACKAGE_TOOLS = {
    'debian': 'apt-get install -y',
    'fedora': 'dnf install',
    'gentoo': 'emerge',
    'linuxmint': 'apt-get install -y',
    'raspbian': 'apt-get install -y',
    'suse': 'zypper in',
    'ubuntu': 'apt-get install -y',
}


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Chkdeps,
                defaults=[],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.console = None

    def _get_distribution(self):
        distribution = distro.linux_distribution(full_distribution_name=False)
        self.console.print(f"Detected system: {' '.join(distribution)}")
        distribution = distribution[0].lower()
        if distribution not in PACKAGE_TOOLS:
            LOGGER.warning(
                "WARNING: Unknown distribution."
                " Can't suggest packages to install"
            )
        return distribution

    def cmd_set_console(self, console):
        self.console = console

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'chkdeps',
            help=_("Check that all required dependencies are installed")
        )
        p.add_argument(
            "--yes", "-y",
            required=False, default=False, action='store_true'
        )

    def cmd_run(self, console, args):
        if args.command != 'chkdeps':
            return None
        auto = args.yes

        if auto:
            LOGGER.warning("Confirmation disabled")

        distribution = self._get_distribution()

        missing = collections.defaultdict(dict)
        self.core.call_all(Chkdeps.chkdeps, missing)

        if len(missing) > 0:
            console.print(_("Missing dependencies:"))
            for (dep_name, distrib_packages) in missing.items():
                console.print(_("- {dep_name} (package: {pkg_name})").format(
                    dep_name=dep_name,
                    pkg_name=(
                        distrib_packages[distribution]
                        if distribution in distrib_packages
                        else _("UNKNOWN")
                    )
                ))

        if distribution in PACKAGE_TOOLS:
            command = PACKAGE_TOOLS[distribution]
            if os.getuid() != 0:
                command = "sudo {}".format(command)
        else:
            command = None
        has_pkg = False
        for (dep_name, distrib_packages) in missing.items():
            if distribution in distrib_packages:
                if command is not None:
                    command += " " + distrib_packages[distribution]
                has_pkg = True

        if has_pkg and command is not None:
            console.print("")
            console.print(_("Suggested command:"))
            console.print("  " + command)
            console.print("")
            if not auto:
                r = util.ask_confirmation(
                    console,
                    _("Do you want to run this command now ?"),
                    default_interactive='n',
                    default_non_interactive='n',
                )
                if r != 'y':
                    return {
                        "missing": missing,
                        "command": command,
                    }
            console.print("Running command ...")
            r = os.system(command)
            console.print("Command returned {}".format(r))
            if r != 0:
                sys.exit(r)
        elif len(missing) > 0:
            console.print(
                _("Don't know how to install missing dependencies. Sorry.")
            )
        else:
            console.print(_("Nothing to do."))

        return {
            "missing": missing,
            "command": command,
        }
