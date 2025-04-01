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
import openpaperwork_core.promise

from .. import _


DEFAULT_RESOLUTION = 300


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": "mainloop",
                "defaults": ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                "interface": "scan2doc",
                "defaults": ["paperwork_backend.docscan.scan2doc"],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.out = []

    def cmd_complete_argparse(self, parser):
        scan_parser = parser.add_parser(
            'scan', help=_("Scan pages")
        )
        scan_parser.add_argument(
            "--doc_id", "-d", help=_(
                "Document to which the scanned pages must be added"
            )
        )
        scan_parser.add_argument("source_id")

    def cmd_run(self, console, args):
        if args.command != 'scan':
            return None

        doc_url = None
        if args.doc_id is not None:
            doc_url = self.core.call_success("doc_id_to_url", args.doc_id)

        promise = self.core.call_success(
            "scan2doc_promise",
            doc_id=args.doc_id, doc_url=doc_url,
            source_id=args.source_id
        )
        self.core.call_success("scan_schedule", promise)

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        return True
