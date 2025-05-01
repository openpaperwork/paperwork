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

from openpaperwork_core.interfaces.i18n import I18n
from openpaperwork_core.interfaces.print import Print
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.index import Index

from paperwork_shell import _
from paperwork_shell.interfaces.renderer import DocRendererFactory


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            # if there are no doc_renderer loaded, nothing it displayed, which
            # may be fine.
            # (see paperwork-json)
            {
                "interface": DocRendererFactory,
                "defaults": [],
            },
            {
                "interface": DocStorage,
                "defaults": ['paperwork_backend.model.workdir'],
            },
            {
                'interface': I18n,
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                "interface": Index,
                "defaults": ['paperwork_backend.index.shell'],
            },
            {
                "interface": Print,
                "defaults": [],
                "optional": True,
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'search', help=_("Search keywords in documents")
        )
        p.add_argument(
            '--limit', '-l', type=int, default=50,
            help=_("Maximum number of results (default: 50)")
        )
        p.add_argument(
            'keywords', nargs='*', default=[],
            help=_("Search keywords (none means all documents)")
        )

    def cmd_run(self, console, args):
        if args.command != 'search':
            return None

        keywords = " ".join(args.keywords)

        docs = []
        self.core.call_all(Index.index_search, docs, keywords, args.limit)
        docs.sort(reverse=True)

        renderers = []
        self.core.call_all(DocRendererFactory.doc_renderer_get, renderers)
        renderer = renderers[-1]

        for (doc_id, doc_url) in docs:
            header = _("Document id: %s") % doc_id
            self.core.call_all(Print.print, header)

            doc_date = self.core.call_success(DocStorage.doc_get_date_by_id, doc_id)
            doc_date = self.core.call_success(I18n.i18n_date_short, doc_date)
            header = _("Document date: %s") % doc_date
            self.core.call_all(Print.print, header)

            if renderer is None:
                continue
            if doc_url is None:
                LOGGER.warning("Failed to get URL of document %s", doc_id)
                continue
            lines = renderer.get_preview_output(
                doc_id, doc_url, shutil.get_terminal_size()
            )
            for line in lines:
                self.core.call_all(Print.print, line)
            self.core.call_all(Print.print, "")
        self.core.call_success(Print.print_flush)

        return [doc[0] for doc in docs]
