#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2024  Jerome Flesch
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
import openpaperwork_core

from .. import _


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()

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

        source_doc_url = self.core.call_success("doc_id_to_url", source_doc_id)

        console.print(f"Copying {source_doc_id}")
        dest_doc_url = self.core.call_success("doc_copy_by_url", source_doc_url)
        dest_doc_id = self.core.call_success("doc_url_to_id", dest_doc_url)
        console.print(f"New document: {dest_doc_id}")

        self.core.call_success("transaction_simple", [
            ("add", dest_doc_id),
        ])
        self.core.call_success("mainloop_quit_graceful")
        self.core.call_success("mainloop")
        return dest_doc_id
