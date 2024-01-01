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
                "interface": "pages",
                "defaults": [
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.thumbnail',
                ],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'move', help=_("Move a page")
        )
        p.add_argument(
            'source_doc_id',
            help=_("Source document")
        )
        p.add_argument(
            'source_page', type=int,
            help=_("Page to move")
        )
        p.add_argument(
            'dest_doc_id',
            help=_("Destination document")
        )
        p.add_argument(
            'dest_page', type=int,
            help=_("Target page number")
        )

    def cmd_run(self, console, args):
        if args.command != 'move':
            return None

        source_doc_id = args.source_doc_id
        source_page_idx = args.source_page - 1
        dest_doc_id = args.dest_doc_id
        dest_page_idx = args.dest_page - 1

        source_doc_url = self.core.call_success("doc_id_to_url", source_doc_id)
        dest_doc_url = self.core.call_success("doc_id_to_url", dest_doc_id)

        self.core.call_all(
            "page_move_by_url",
            source_doc_url, source_page_idx,
            dest_doc_url, dest_page_idx
        )

        self.core.call_success("transaction_simple", [
            ("upd", source_doc_id),
            ("upd", dest_doc_id),
        ])
        self.core.call_success("mainloop_quit_graceful")
        self.core.call_success("mainloop")

        return True
