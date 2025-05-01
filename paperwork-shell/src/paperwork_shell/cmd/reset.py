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
import logging
import shutil

import rich.text

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.pillow import Pillow
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.pages import PageManagement

from paperwork_shell import _
from paperwork_shell.cmd import util
from paperwork_shell.interfaces.renderer import ImgRenderer


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": DocStorage,
                "defaults": ["paperwork_backend.model.workdir"],
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
            {
                "interface": ImgRenderer,
                "defaults": [
                    "paperwork_shell.display.docrendering.img"
                ],
            },
            {
                'interface': Mainloop,
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                "interface": PageImg,
                "defaults": [
                    "paperwork_backend.model.img",
                    "paperwork_backend.model.pdf",
                ]
            },
            {
                "interface": PageManagement,
                "defaults": ["paperwork_backend.model.img_overlay"],
            },
            {
                "interface": Pillow,
                "defaults": [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
        ]

    def cmd_complete_argparse(self, parser):
        reset_parser = parser.add_parser(
            'reset', help=_("Reset a page to its original content")
        )
        # for safety, we mark the argument --pages as required
        reset_parser.add_argument('--pages', '-p', type=str, required=True)
        reset_parser.add_argument('doc_id')

    def _show_page(self, console, doc_url, page_idx):
        page_url = self.core.call_success(
            PageImg.page_get_img_url, doc_url, page_idx
        )
        img = self.core.call_success(Pillow.url_to_pillow, page_url)

        terminal_width = shutil.get_terminal_size()[0] - 1
        img = self.core.call_success(
            ImgRenderer.img_render, img, terminal_width=terminal_width
        )
        if img is None:
            return
        for line in img:
            console.print(rich.text.Text(line))
        console.print("")

    def cmd_run(self, console, args):
        if args.command != 'reset':
            return None

        doc_id = args.doc_id
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)
        pages = util.parse_page_list(args)
        out = []

        for page_idx in pages:
            out.append((doc_id, page_idx))
            console.print(
                _("Reseting document {} page {} ...").format(
                    doc_id, page_idx
                )
            )
            console.print(_("Original:"))
            self._show_page(doc_url, page_idx)

            self.core.call_all(PageManagement.page_reset_by_url, doc_url, page_idx)

            console.print(_("Reseted:"))
            self._show_page(doc_url, page_idx)
            console.print("")

        self.core.call_success(DocTransactionManager.transaction_simple, [("upd", doc_id),])
        self.core.call_success(Mainloop.mainloop_quit_graceful)
        self.core.call_success(Mainloop.mainloop)

        console.print(_("Done"))
        console.print(_("All done !"))

        return out
