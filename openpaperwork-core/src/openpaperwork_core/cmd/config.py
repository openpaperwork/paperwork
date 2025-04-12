#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2025 Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.
import datetime
import logging

from openpaperwork_core import _
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.display import Display
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core


LOGGER = logging.getLogger(__name__)


def bool_from_str(s):
    s = s.strip()
    if s == "" or s == "0" or s.lower() == "false":
        return False
    return True


# Only basic types are handled by shell commands
CMD_VALUE_TYPES = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool_from_str,
}

DATE_FORMAT = "%Y-%m-%d"

TO_JSON = {
    datetime.date: lambda x: x.strftime(DATE_FORMAT)
}


class Plugin(
    openpaperwork_core.PluginBase,
    Shell
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
            {
                "interface": Display,
                "defaults": [],
                "optional": True,
            },
        ]

    def cmd_complete_argparse(self, parser):
        config_parser = parser.add_parser(
            'config', help=_("Manage Paperwork configuration")
        )

        subparser = config_parser.add_subparsers(
            help=_("sub-command"), dest='subcommand', required=True
        )

        get_parser = subparser.add_parser(
            'get', help=_("Get a value from Paperwork's configuration")
        )
        get_parser.add_argument('opt_name')

        put_parser = subparser.add_parser(
            'put', help=_("Set a value in Paperwork's configuration")
        )
        put_parser.add_argument('opt_name')
        put_parser.add_argument('type', help=_("See 'config list_type'"))
        put_parser.add_argument('value')

        subparser.add_parser(
            'show', help=_("Show Paperwork's configuration")
        )

        subparser.add_parser(
            'list_types', help=_(
                "Show value types you can use from command line"
            )
        )

    def cmd_run(self, console, args):
        if args.command != 'config':
            return None
        if args.subcommand == "get":
            return self._cmd_get(args.opt_name)
        elif args.subcommand == "put":
            return self._cmd_put(args.opt_name, args.type, args.value)
        elif args.subcommand == "show":
            return self._cmd_show()
        elif args.subcommand == "list_types":
            return self._cmd_list_types()
        else:
            return None

    def _cmd_get(self, opt_name):
        v = self.core.call_success(Config.config_get, opt_name)
        if v is None:
            LOGGER.warning("No such option '%s'", opt_name)
            return None
        self.core.call_all(Display.print, f"{opt_name} = {v}")
        self.core.call_success(Display.print_flush)
        return {opt_name: v}

    def _cmd_put(self, opt_name, vtype, value):
        value = CMD_VALUE_TYPES[vtype](value)
        self.core.call_success(Display.print, f"{opt_name} = {value}")
        self.core.call_success(Display.print_flush)
        self.core.call_all(Config.config_put, opt_name, value)
        self.core.call_all(Config.config_save)
        return {opt_name: value}

    def _cmd_show(self):
        opts = self.core.call_success(Config.config_list_options)
        out = {}
        opts.sort()
        for opt in opts:
            v = self.core.call_success(Config.config_get, opt)
            if type(v) in TO_JSON:
                v = TO_JSON[type(v)](v)
            out[opt] = v
            self.core.call_success(
                Display.print, f"{opt} = {out[opt]} ({type(v).__name__})"
            )
        self.core.call_success(Display.print_flush)
        return out

    def _cmd_list_types(self):
        r = list(CMD_VALUE_TYPES.keys())
        self.core.call_success(Display.print, str(r))
        self.core.call_success(Display.print_flush)
        return r
