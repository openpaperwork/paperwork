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

from . import util
from .. import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": "ocr",
                "defaults": ['paperwork_backend.guesswork.ocr.pyocr'],
            },
            {
                "interface": "ocr_settings",
                "defaults": ['paperwork_backend.pyocr'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'ocr', help=_(
                "OCR document or pages"
            )
        )
        p.add_argument(
            'doc_id', type=str,
            help=_("Document on which OCR must be run")
        )
        p.add_argument(
            '--pages', '-p', type=str,
            help=_(
                "Pages to OCR"
                " (single integer, range or comma-separated list,"
                " default: all pages)"
            )
        )

    def cmd_run(self, console, args):
        if args.command != 'ocr':
            return None

        if self.core.call_success("ocr_is_enabled") is None:
            console.print("OCR is disabled")
            return []

        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        pages = util.parse_page_list(args)
        if pages is None:
            nb_pages = self.core.call_success(
                "doc_get_nb_pages_by_url", doc_url
            )
            pages = range(0, nb_pages)

        out = []

        for page_idx in pages:
            console.print(
                _(
                    "Running OCR on"
                    " document {doc_id} page {page_idx} ..."
                ).format(
                    doc_id=doc_id, page_idx=(page_idx + 1)
                )
            )

            self.core.call_all("ocr_page_by_url", doc_url, page_idx)

            console.print(_("Done"))

            out.append((doc_id, page_idx))

        console.print(_("All done !"))

        return out
