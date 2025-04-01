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
import logging
import shutil

import openpaperwork_core

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
        return [
            # if there are no doc_renderer loaded, nothing it displayed, which
            # may be fine.
            # (see paperwork-json)
            # {
            #     "interface": "doc_renderer",
            #     "defaults": [],
            # },
            {
                "interface": "document_storage",
                "defaults": ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                "interface": "index",
                "defaults": ['paperwork_backend.index.shell'],
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
        self.core.call_all("index_search", docs, keywords, args.limit)
        docs.sort(reverse=True)

        renderers = []
        self.core.call_all("doc_renderer_get", renderers)
        renderer = renderers[-1]

        for (doc_id, doc_url) in docs:
            header = _("Document id: %s") % doc_id
            self.core.call_all("print", header)

            doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
            doc_date = self.core.call_success("i18n_date_short", doc_date)
            header = _("Document date: %s") % doc_date
            self.core.call_all("print", header)

            if renderer is None:
                continue
            if doc_url is None:
                LOGGER.warning("Failed to get URL of document %s", doc_id)
                continue
            lines = renderer.get_preview_output(
                doc_id, doc_url, shutil.get_terminal_size()
            )
            for line in lines:
                self.core.call_all("print", line)
            self.core.call_all("print", "")
        self.core.call_success("print_flush")

        return [doc[0] for doc in docs]
