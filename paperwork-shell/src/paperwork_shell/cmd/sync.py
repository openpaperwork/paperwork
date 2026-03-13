#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2025  Jerome Flesch
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

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.sync import SyncListener

from paperwork_shell import _


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
    SyncListener,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=["openpaperwork_core.mainloop.asyncio"],
            ),
            openpaperwork_core.Dependency(
                interface=DocTransactionManager,
                defaults=['paperwork_backend.sync'],
            ),
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

        self.core.call_all(DocTransactionManager.transaction_sync_all)
        self.core.call_success(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)
        console.print(_("All done !"))

        # ensure order of documents to make testing easier and ensure
        # behaviour consistency
        for actions in self.changes.values():
            for docs in actions.values():
                docs.sort()
        return dict(self.changes)
