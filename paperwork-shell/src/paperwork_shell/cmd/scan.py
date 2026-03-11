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
import openpaperwork_core

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.shell import Shell

from paperwork_backend import _
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.scan import Scan
from paperwork_backend.interfaces.scan2doc import Scan2Doc


DEFAULT_RESOLUTION = 300


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
                "interface": Mainloop,
                "defaults": ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                "interface": Scan,
                "defaults": ["paperwork_backend.docscan.libinsane"],
            },
            {
                "interface": Scan2Doc,
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
            doc_url = self.core.call_success(DocStorage.doc_id_to_url, args.doc_id)

        promise = self.core.call_success(
            Scan2Doc.scan2doc_promise,
            doc_id=args.doc_id, doc_url=doc_url,
            source_id=args.source_id
        )
        self.core.call_success(Scan.scan_schedule, promise)

        self.core.call_success(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)

        return True
