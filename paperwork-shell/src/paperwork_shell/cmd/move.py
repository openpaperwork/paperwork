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
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.pages import PageManagement

from paperwork_shell import _


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=['openpaperwork_core.mainloop.asyncio'],
            ),
            openpaperwork_core.Dependency(
                interface=PageManagement,
                defaults=[
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.thumbnail',
                ],
            ),
            openpaperwork_core.Dependency(
                interface=DocTransactionManager,
                defaults=['paperwork_backend.sync'],
            ),
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

        source_doc_url = self.core.call_success(DocStorage.doc_id_to_url, source_doc_id)
        dest_doc_url = self.core.call_success(DocStorage.doc_id_to_url, dest_doc_id)

        self.core.call_all(
            PageManagement.page_move_by_url,
            source_doc_url, source_page_idx,
            dest_doc_url, dest_page_idx
        )

        self.core.call_success(DocTransactionManager.transaction_simple, [
            ("upd", source_doc_id),
            ("upd", dest_doc_id),
        ])
        self.core.call_success(Mainloop.mainloop_quit_graceful)
        self.core.call_success(Mainloop.mainloop)

        return True
