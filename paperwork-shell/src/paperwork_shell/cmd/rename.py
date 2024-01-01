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
import rich.text

import openpaperwork_core

from .. import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                "interface": "document_storage",
                "defaults": ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': 'transaction_manager',
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

        source_doc_url = self.core.call_success("doc_id_to_url", source_doc_id)
        dest_doc_url = self.core.call_success(
            "doc_id_to_url", dest_doc_id, existing=False
        )

        console.print(rich.text.Text(
            f"Renaming: {source_doc_url} --> {dest_doc_url}"
        ))

        self.core.call_all("doc_rename_by_url", source_doc_url, dest_doc_url)
        self.core.call_success(
            "transaction_simple",
            [
                ('del', source_doc_id),
                ('add', dest_doc_id),
            ]
        )
        self.core.call_success("mainloop_quit_graceful")
        self.core.call_success("mainloop")

        console.print(rich.text.Text(
            f"{source_doc_id} renamed into {dest_doc_id}"
        ))

        return True
