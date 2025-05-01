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
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager

from paperwork_shell import _


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": DocStorage,
                "defaults": ['paperwork_backend.model.workdir'],
            },
            {
                'interface': Mainloop,
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'copy', help=_("Copy a document")
        )
        p.add_argument(
            'source_doc_id',
            help=_("Source document")
        )

    def cmd_run(self, console, args):
        if args.command != 'copy':
            return None

        source_doc_id = args.source_doc_id

        source_doc_url = self.core.call_success(DocStorage.doc_id_to_url, source_doc_id)

        console.print(f"Copying {source_doc_id}")
        dest_doc_url = self.core.call_success(DocStorage.doc_copy_by_url, source_doc_url)
        dest_doc_id = self.core.call_success(DocStorage.doc_url_to_id, dest_doc_url)
        console.print(f"New document: {dest_doc_id}")

        self.core.call_success(DocTransactionManager.transaction_simple, [
            ("add", dest_doc_id),
        ])
        self.core.call_success(Mainloop.mainloop_quit_graceful)
        self.core.call_success(Mainloop.mainloop)
        return dest_doc_id
