#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2019  Jerome Flesch
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
import importlib
import logging

from .. import (_, PluginBase)


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        application = self.core.call_success("config_get_plugin_list_name")

        config_parser = parser.add_parser(
            'plugins', help=(_("Manage %s plugins") % application)
        )

        subparser = config_parser.add_subparsers(
            help=_("sub-command"), dest='subcommand', required=True
        )

        subparser.add_parser(
            'list', help=(
                _("Show plugins enabled for %s") % application
            )
        )

        p = subparser.add_parser(
            'add', help=(
                _("Add plugin in %s") % application
            )
        )
        p.add_argument('plugin_name')
        p.add_argument(
            '--no_auto', '-n', action="store_true",
            help=_("Do not correct dependencies automatically")
        )

        p = subparser.add_parser(
            'remove', help=(
                _("Remove plugin from %s") % application
            )
        )
        p.add_argument('plugin_name')
        p.add_argument(
            '--no_auto', '-n', action="store_true",
            help=_("Do not correct dependencies automatically")
        )

        subparser.add_parser(
            'reset', help=(_(
                "Clean up your mess by reseting the plugin list to its"
                " default value"
            ))
        )

        p = subparser.add_parser(
            'show', help=(
                _("Show information regarding a plugin (must be enabled)")
            )
        )
        p.add_argument('plugin_name')

    def cmd_run(self, console, args):
        if args.command != 'plugins':
            return None
        elif args.subcommand == "list":
            return self._cmd_list_plugins(console)
        elif args.subcommand == "add":
            return self._cmd_add_plugin(
                console, args.plugin_name, not args.no_auto
            )
        elif args.subcommand == "remove":
            return self._cmd_remove_plugin(
                console, args.plugin_name, not args.no_auto
            )
        elif args.subcommand == "reset":
            return self._cmd_reset_plugins(console)
        elif args.subcommand == "show":
            return self._cmd_show_plugin(console, args.plugin_name)
        else:
            return None

    def _cmd_add_plugin(
                self, console, plugin_name, auto=True, added=set(), save=True
            ):
        added.add(plugin_name)

        if auto:
            # Load the plugin, and check that all its dependencies are
            # satisfied.
            # Do not use the core to load it, otherwise we won't be able
            # to use 'call_success()' or 'call_all().
            try:
                module = importlib.import_module(plugin_name)
            except ModuleNotFoundError:
                console.print(
                    _("Error: Plugin '%s' not found") % plugin_name
                )
                return False
            plugin = module.Plugin()
            deps = plugin.get_deps()
            for dep in deps:
                try:
                    actives = self.core.get_by_interface(dep['interface'])
                    if len(actives) > 0:
                        continue
                except KeyError:
                    pass
                for default in dep['defaults']:
                    if default in added:
                        continue
                    console.print(
                        _(
                            "Adding plugin '{plugin_name}' to satisfy"
                            " dependency of '{other_plugin_name}' on interface"
                            " '{interface}'"
                        ).format(
                            plugin_name=default,
                            other_plugin_name=plugin_name,
                            interface=dep['interface']
                        )
                    )
                    r = self._cmd_add_plugin(
                        default, auto=True, added=added, save=False
                    )
                    if not r:
                        return r

        self.core.call_all("config_add_plugin", plugin_name)
        if save:
            self.core.call_all("config_save")
        console.print(_("Plugin {} added").format(plugin_name))
        return True

    def _cmd_remove_plugin(
            self, console, plugin_name, auto=True, removed=set(), save=True):
        removed.add(plugin_name)

        if auto:
            # look for plugins depending on this one
            # if they have no other plugin satisfying their dependency,
            # remove them too.
            for other_plugin in self.core.get_active_plugins():
                if other_plugin in removed:
                    continue
                deps = self.core.get_deps(other_plugin)
                for dep in deps:
                    actives = dep['actives']
                    actives = actives.difference(removed)
                    if len(actives) <= 0:
                        console.print(
                            _(
                                "Removing plugin '{plugin_name}' due to"
                                " missing dependency '{interface}'"
                            ).format(
                                plugin_name=other_plugin,
                                interface=dep['interface']
                            )
                        )
                        self._cmd_remove_plugin(
                            console, other_plugin, auto=auto, removed=removed,
                            save=False
                        )
                        break

        self.core.call_all("config_remove_plugin", plugin_name)
        if save:
            self.core.call_all("config_save")
        console.print(_("Plugin {} removed").format(plugin_name))
        return True

    def _cmd_list_plugins(self, console):
        plugins = self.core.call_success("config_list_plugins")
        console.print("  " + _("Active plugins:"))
        for plugin in plugins:
            console.print(plugin)
        return list(plugins)

    def _cmd_reset_plugins(self, console):
        self.core.call_success("config_reset_plugins")
        self.core.call_all("config_save")
        console.print("Plugin list reseted")
        return True

    def _print_columns(self, console, columns):
        out = ""
        for (column_size, string) in columns:
            out += "| "
            out += ("{:" + str(column_size) + "}").format(string)
        out = out[1:]
        console.print(out)

    def _get_printable_deps(
            self, plugin_name,
            parents_requirements=set(), depth=0, already_printed=set()):
        header = "|   " * (depth - 1)

        try:
            plugin = self.core.get_by_name(plugin_name)
        except KeyError:
            # Plugin not loaded --> can't get the info
            yield (
                header + "|-- " + plugin_name,
                "(not loaded)",
            )
            return

        str_plugin_name = plugin_name
        if plugin_name in already_printed:
            str_plugin_name = plugin_name + " (dup)"

        interfaces = plugin.get_interfaces()
        interfaces = [i for i in interfaces if i in parents_requirements]
        if len(interfaces) <= 0:
            interfaces = [""]

        for (idx, interface) in enumerate(interfaces):
            if idx == 0:
                yield (
                    header + "|-- " + str_plugin_name
                    if depth > 0 else
                    str_plugin_name,
                    interface,
                )
            else:
                yield (
                    header + "|   |",
                    interface,
                )

        if plugin_name in already_printed:
            return []
        already_printed.add(plugin_name)

        deps = plugin.get_deps()

        requirements = {d['interface'] for d in deps}
        requirements.update(parents_requirements)

        plugin_names = set()
        for (idx, dep) in enumerate(deps):
            plugins = self.core.get_by_interface(dep['interface'])
            plugin_names.update({plugin.__module__ for plugin in plugins})
            plugin_names.update(dep['defaults'])

        plugin_names = list(plugin_names)
        plugin_names.sort()
        for (idx, plugin_name) in enumerate(plugin_names):
            for line in self._get_printable_deps(
                    plugin_name, requirements, depth + 1, already_printed):
                yield line

    def _cmd_show_plugin(self, console, plugin_name):
        try:
            plugin = self.core.get_by_name(plugin_name)
        except KeyError:
            console.print(_("Plugin '%s' not enabled.") % plugin_name)
            return {}

        console.print(_("Plugin '%s':") % plugin_name)
        console.print("* " + _("Implements:"))
        for interf in plugin.get_interfaces():
            console.print("  + " + interf)
        console.print("* " + _("Depends on:"))
        for dep in plugin.get_deps():
            console.print("  + " + dep['interface'])
            for default in dep['defaults']:
                console.print("    - " + (_("suggested: %s") % default))

        console.print("")

        deps = list(self._get_printable_deps(plugin_name))

        column_headers = (
            _("Plugin name"),
            _("Interface"),
        )

        column_sizes = [len(c) + 1 for c in column_headers]
        for d in deps:
            for (idx, column_value) in enumerate(d):
                column_sizes[idx] = max(
                    column_sizes[idx], len(column_value) + 1
                )
        total = sum(column_sizes) + (2 * len(column_sizes))

        self._print_columns(
            console,
            (
                (column_sizes[0], _("Plugin name")),
                (column_sizes[1], _("Interface")),
            )
        )
        console.print("-" * total)
        for d in deps:
            self._print_columns(
                console, [
                    (column_sizes[idx], column_value)
                    for (idx, column_value) in enumerate(d)
                ]
            )

        return {
            'interface': plugin.get_interfaces(),
            'deps': plugin.get_deps()
        }
