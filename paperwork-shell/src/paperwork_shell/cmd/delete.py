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
import sys

from openpaperwork_core.cmd.util import ask_confirmation
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.pages import PageManagement

from paperwork_shell.cmd.util import parse_page_list
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
            'delete', help=_("Delete a document or a page")
        )
        p.add_argument(
            '--pages', '-p', type=str, required=False,
            help=_(
                "Pages to delete"
                " (single integer, range or comma-separated list,"
                " default: all pages)"
            )
        )
        p.add_argument(
            'doc_ids', nargs='*', default=[],
            help=_("Target documents")
        )

    def cmd_run(self, console, args):
        if args.command != 'delete':
            return None

        doc_ids = args.doc_ids

        for doc_id in doc_ids:
            if "/" in doc_id or "\\" in doc_id or ".." in doc_id:
                sys.stderr.write(f"Invalid doc_id: {doc_id}")
                sys.exit(2)

        pages = parse_page_list(args)

        del_doc_msg = _("Deleting document {doc_id} ...")
        del_page_msg = _("Deleting page {page_idx} of document {doc_id} ...")

        for doc_id in doc_ids:
            if pages is None:
                r = ask_confirmation(
                    console,
                    _("Delete document %s ?") % str(doc_id),
                    default_interactive='n',
                    default_non_interactive='y',
                )
            else:
                r = ask_confirmation(
                    _(
                        "Delete page(s)"
                        " {page_indexes} of document {doc_id} ?".format(
                            page_indexes=str([p + 1 for p in pages]),
                            doc_id=str(doc_id)
                        )
                    ),
                    default_interactive='n',
                    default_non_interactive='y',
                )
            if r != 'y':
                continue

            if pages is None:
                console.print(del_doc_msg.format(doc_id=doc_id))
                self.core.call_all(DocStorage.storage_delete_doc_id, doc_id)
            else:
                for page in pages:
                    doc_url = self.core.call_success(
                        DocStorage.doc_id_to_url, doc_id
                    )
                    console.print(del_page_msg.format(
                        page_idx=(page + 1), doc_id=doc_id)
                    )
                    self.core.call_all(PageManagement.page_delete_by_url, doc_url, page)

        self.core.call_success(
            DocTransactionManager.transaction_simple, [
                # transaction_simple() will automatically replace the change
                # 'upd' by 'del' for the documents that don't exist anymore
                ("upd", doc_id) for doc_id in doc_ids
            ]
        )
        self.core.call_success(Mainloop.mainloop_quit_graceful)
        self.core.call_success(Mainloop.mainloop)

        return True
