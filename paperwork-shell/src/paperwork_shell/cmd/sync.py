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
import collections

import openpaperwork_core

from .. import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": "syncable",
                "defaults": [
                    "paperwork_backend.guesswork.label.sklearn",
                    "paperwork_backend.guesswork.ocr.pyocr",
                    "paperwork_backend.index.whoosh",
                    "paperwork_backend.model.labels",
                ],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.changes = collections.defaultdict(
            # we cannot use sets here because sets are not JSON-serializable
            lambda: collections.defaultdict(list)
        )

    def cmd_complete_argparse(self, parser):
        parser.add_parser('sync', help=_(
            "Synchronize the index(es) with the content of the work directory"
        ))

    def on_sync(self, name, status, key):
        self.changes[name][status].append(key)

    def cmd_run(self, console, args):
        if args.command != 'sync':
            return None

        console.print(_("Synchronizing with work directory ..."))

        self.changes = collections.defaultdict(
            # we cannot use sets here because sets are not JSON-serializable
            lambda: collections.defaultdict(list)
        )

        self.core.call_all("transaction_sync_all")
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")
        console.print(_("All done !"))

        # ensure order of documents to make testing easier and ensure
        # behaviour consistency
        for actions in self.changes.values():
            for docs in actions.values():
                docs.sort()
        return dict(self.changes)
