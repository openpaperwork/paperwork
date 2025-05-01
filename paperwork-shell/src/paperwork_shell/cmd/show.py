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
import shutil

from openpaperwork_core.interfaces.i18n import I18n
from openpaperwork_core.interfaces.print import Print
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import Docs

from paperwork_shell import _
from paperwork_shell.cmd import util
from paperwork_shell.interfaces.renderer import DocRendererFactory


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        # if there are no doc_renderer loaded, nothing is displayed, which
        # may be fine.
        # (see paperwork-json)
        return [
            {
                "interface": Docs,
                "defaults": ["paperwork_backend.model"],
            },
            {
                "interface": DocRendererFactory,
                "defaults": [
                    "paperwork_shell.display.doc_renderer",
                    "paperwork_shell.display.docrendering.extra_text",
                    "paperwork_shell.display.docrendering.img",
                    "paperwork_shell.display.docrendering.labels",
                    "paperwork_shell.display.docrendering.text",
                ],
            },
            {
                'interface': DocStorage,
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': I18n,
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                "interface": Print,
                "defaults": [
                    "openpaperwork_core.display.print",
                    "paperwork_shell.display.rich",
                ],
                "optional": True,
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
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)
        if doc_url is None:
            return False
        nb_pages = self.core.call_success(Docs.doc_get_nb_pages_by_url, doc_url)
        if nb_pages is None or nb_pages <= 0:
            return False

        pages = util.parse_page_list(args)
        if pages is None:
            pages = range(0, nb_pages)

        renderers = []
        self.core.call_all(DocRendererFactory.doc_renderer_get, renderers)
        assert len(renderers) > 0
        renderer = renderers[-1]

        header = _("Document id: %s") % doc_id
        self.core.call_success(Print.print, header)
        self.core.call_success(Print.print, "=" * len(header))

        doc_date = self.core.call_success(DocStorage.doc_get_date_by_id, doc_id)
        doc_date = self.core.call_success(I18n.i18n_date_short, doc_date)
        header = _("Document date: %s") % doc_date
        self.core.call_success(Print.print, header)

        lines = renderer.get_doc_output(
            doc_id, doc_url, shutil.get_terminal_size()
        )
        for line in lines:
            self.core.call_success(Print.print, line)
        self.core.call_success(Print.print, "")

        for page_nb in pages:
            self.core.call_success(Print.print, "")
            header = _("Page %d") % (page_nb + 1)
            self.core.call_success(Print.print, header)
            self.core.call_success(Print.print, ("-" * len(header)) + "\n")
            lines = renderer.get_page_output(
                doc_id, doc_url, page_nb, shutil.get_terminal_size()
            )
            for line in lines:
                self.core.call_success(Print.print, line)
            self.core.call_success(Print.print, "")

        self.core.call_success(Print.print_flush)

        return {
            'document': renderer.get_doc_infos(doc_id, doc_url),
            'pages': {
                page_nb: renderer.get_page_infos(doc_id, doc_url, page_nb)
                for page_nb in pages
            },
        }
