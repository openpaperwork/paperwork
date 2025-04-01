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
import shutil

import openpaperwork_core

from . import util
from .. import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
        # if there are no doc_renderer loaded, nothing is displayed, which
        # may be fine.
        # (see paperwork-json)
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser('show', help=_(
            "Show the content of a document"
        ))
        p.add_argument('doc_id')
        p.add_argument(
            '--pages', '-p', required=False,
            help="Pages to show: 1,4 or 1-10 (default: all)"
        )

    def cmd_run(self, console, args):
        if args.command != 'show':
            return None

        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        if doc_url is None:
            return False
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None or nb_pages <= 0:
            return False

        pages = util.parse_page_list(args)
        if pages is None:
            pages = range(0, nb_pages)

        renderers = []
        self.core.call_all("doc_renderer_get", renderers)
        assert len(renderers) > 0
        renderer = renderers[-1]

        header = _("Document id: %s") % doc_id
        self.core.call_success("print", header)
        self.core.call_success("print", "=" * len(header))

        doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
        doc_date = self.core.call_success("i18n_date_short", doc_date)
        header = _("Document date: %s") % doc_date
        self.core.call_success("print", header)

        lines = renderer.get_doc_output(
            doc_id, doc_url, shutil.get_terminal_size()
        )
        for line in lines:
            self.core.call_success("print", line)
        self.core.call_success("print", "")

        for page_nb in pages:
            self.core.call_success("print", "")
            header = _("Page %d") % (page_nb + 1)
            self.core.call_success("print", header)
            self.core.call_success("print", ("-" * len(header)) + "\n")
            lines = renderer.get_page_output(
                doc_id, doc_url, page_nb, shutil.get_terminal_size()
            )
            for line in lines:
                self.core.call_success("print", line)
            self.core.call_success("print", "")

        self.core.call_success("print_flush")

        return {
            'document': renderer.get_doc_infos(doc_id, doc_url),
            'pages': {
                page_nb: renderer.get_page_infos(doc_id, doc_url, page_nb)
                for page_nb in pages
            },
        }
