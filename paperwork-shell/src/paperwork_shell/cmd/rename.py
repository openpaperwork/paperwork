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
import rich.text

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend import _
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager


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
            'rename', help=_("Change a document identifier")
        )
        p.add_argument(
            'source_doc_id',
            help=_("Document to rename")
        )
        p.add_argument(
            'dest_doc_id',
            help=_("New name for the document")
        )

    def cmd_run(self, console, args):
        if args.command != 'rename':
            return None

        source_doc_id = args.source_doc_id
        dest_doc_id = args.dest_doc_id

        source_doc_url = self.core.call_success(DocStorage.doc_id_to_url, source_doc_id)
        dest_doc_url = self.core.call_success(
            DocStorage.doc_id_to_url, dest_doc_id, existing=False
        )

        console.print(rich.text.Text(
            f"Renaming: {source_doc_url} --> {dest_doc_url}"
        ))

        self.core.call_all(DocStorage.doc_rename_by_url, source_doc_url, dest_doc_url)
        self.core.call_success(
            DocTransactionManager.transaction_simple,
            [
                ('del', source_doc_id),
                ('add', dest_doc_id),
            ]
        )
        self.core.call_success(Mainloop.mainloop_quit_graceful)
        self.core.call_success(Mainloop.mainloop)

        console.print(rich.text.Text(
            f"{source_doc_id} renamed into {dest_doc_id}"
        ))

        return True
