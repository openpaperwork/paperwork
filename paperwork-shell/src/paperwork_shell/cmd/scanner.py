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
import logging

import openpaperwork_core
import openpaperwork_core.promise

import rich.tree

from .. import _


LOGGER = logging.getLogger(__name__)

DEFAULT_RESOLUTION = 300


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": "mainloop",
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
            {
                "interface": "config",
                "defaults": ['openpaperwork_core.config'],
            },
            {
                "interface": "scan",
                "defaults": ['paperwork_backend.docscan.libinsane'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.out = []

    def cmd_complete_argparse(self, parser):
        scanner_parser = parser.add_parser(
            'scanner', help=_("Manage scanner configuration")
        )
        subparser = scanner_parser.add_subparsers(
            help=_("sub-command"), dest='subcommand', required=True
        )

        subparser.add_parser(
            'list', help=_("List all scanners and their possible settings")
        )

        subparser.add_parser(
            'get', help=_(
                "Show the currently selected scanner and its settings"
            )
        )

        set_scanner = subparser.add_parser(
            'set', help=_("Define which scanner and which settings to use")
        )
        set_scanner.add_argument(
            "device_id", help=_("Scanner to use")
        )
        set_scanner.add_argument(
            "--source", "-s", type=str, required=False,
            help=_(
                "Default source on the scanner to use (if not specified,"
                " one will be selected randomly)"
            )
        )
        set_scanner.add_argument(
            "--resolution", "-r", type=int, required=False,
            help=_("Default resolution (dpi ; default=300)")
        )

    def _get_scanner_info(self, dev, console, dev_id, dev_name):
        console.print(_("Examining scanner {} ...").format(dev_id))
        dev_out = {
            'id': dev_id,
            'name': dev_name,
            'sources': [],
        }
        sources = dev.get_sources()
        for (source_id, source) in sources.items():
            source_out = {
                "id": source_id,
                "resolutions": source.get_resolutions(),
            }
            dev_out['sources'].append(source_out)
        self.out.append(dev_out)
        return dev

    def _on_get_scanner_error(self, exception, scanner_dev_id):
        LOGGER.error(
            "Error while looking for options of %s",
            scanner_dev_id, exc_info=exception
        )

    def _get_scanners_info(self, devs, console):
        for dev in devs:
            # Schedule the promises to examine each scanner separately,
            # so if one failed (for instance on Windows when a scanner is
            # not actually connected), the others can still run.
            dev_id = dev[0]
            dev_name = dev[1]
            promise = openpaperwork_core.promise.Promise(
                self.core, hide_caught_exceptions=True
            )
            promise = promise.then(self.core.call_success(
                "scan_get_scanner_promise", dev_id
            ))
            promise.catch(self._on_get_scanner_error, dev_id)
            promise = promise.then(
                self._get_scanner_info, console, dev_id, dev_name
            )
            promise = promise.then(lambda scanner: scanner.close())
            promise = promise.then(lambda *args, **kwargs: None)
            self.core.call_success("scan_schedule", promise)

    def _list_scanners(self, console):
        self.out = []

        promise = self.core.call_success("scan_list_scanners_promise")
        promise = promise.then(self._get_scanners_info, console)
        self.core.call_success("scan_schedule", promise)
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

    def _print_scanners(self, console):
        console.print("")
        tree = rich.tree.Tree("Scanners")
        for dev in self.out:
            dev_tree = tree.add(dev['name'])
            dev_tree.add(_("ID:") + " " + dev['id'])
            for source in dev['sources']:
                source_tree = dev_tree.add(_("Source:") + " " + source['id'])
                source_tree.add(
                    _("Resolutions:")
                    + " "
                    + str(source['resolutions'])
                )
        console.print(tree)

    def _get_scanner(self, console):
        out = {
            'id': self.core.call_success(
                "config_get", "scanner_dev_id"
            ),
            'source': self.core.call_success(
                "config_get", "scanner_source_id"
            ),
            'resolution': self.core.call_success(
                "config_get", "scanner_resolution"
            ),
        }
        console.print(_("ID:") + " " + str(out['id']))
        console.print(_("Source:") + " " + str(out['source']))
        console.print(_("Resolution:") + " " + str(out['resolution']))
        return out

    def _set_scanner(self, console, args):
        dev_settings = {
            'id': args.device_id,
            'source': args.source,
            'resolution': (
                args.resolution
                if args.resolution is not None
                else DEFAULT_RESOLUTION
            ),
        }

        # In any case, we want to make sure the settings provided are valid
        promise = self.core.call_success(
            "scan_get_scanner_promise", args.device_id
        )

        def check_source(dev):
            sources = dev.get_sources()

            if (
                        dev_settings['source'] is not None
                        and dev_settings['source'] not in sources
                    ):
                console.print(_(
                    "Source {} not found on device."
                    " Using another source"
                ).format(dev_settings['source']))
                dev_settings['source'] = None

            if dev_settings['source'] is None:
                for (source_id, source_obj) in sources.items():
                    if 'flatbed' in source_id.lower():
                        source = (source_id, source_obj)
                        break
                else:
                    source = sources.popitem()
                dev_settings['source'] = source[0]
            else:
                source = (
                    dev_settings['source'],
                    sources[dev_settings['source']]
                )

            console.print(_("Default source:") + " " + dev_settings['source'])

            return source[1]

        promise = promise.then(check_source)

        def check_resolution(source):
            resolutions = source.get_resolutions()
            if dev_settings['resolution'] in resolutions:
                return source
            resolution = min(
                resolutions, key=lambda x: abs(x - dev_settings['resolution'])
            )
            console.print(
                _("Resolution {} not available. Adjusted to {}.").format(
                    dev_settings['resolution'], resolution
                )
            )
            dev_settings['resolution'] = resolution
            return source

        promise = promise.then(check_resolution)

        promise = promise.then(lambda source: source.close())
        self.core.call_success("scan_schedule", promise)
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.core.call_all(
            "config_put", "scanner_dev_id", dev_settings['id']
        )
        self.core.call_all(
            "config_put", "scanner_source_id", dev_settings['source']
        )
        self.core.call_all(
            "config_put", "scanner_resolution",
            dev_settings['resolution']
        )
        self.core.call_all("config_save")

        return self._get_scanner(console)

    def cmd_run(self, console, args):
        if args.command != 'scanner':
            return None

        if args.subcommand == 'list':
            console.print("Looking for scanners ...")
            self._list_scanners(console)
            console.print(f"{len(self.out)} scanners found")
            console.print("")
            self._print_scanners(console)
            return self.out
        elif args.subcommand == 'set':
            return self._set_scanner(console, args)
        elif args.subcommand == 'get':
            return self._get_scanner(console)
        assert False
