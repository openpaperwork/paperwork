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

import rich.text

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_import import ImporterFactory
from paperwork_backend.interfaces.doc_labels import DocLabels
from paperwork_backend.interfaces.doc_transactions import DocTransactionManager
import paperwork_backend.docimport

from paperwork_shell import _


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": Fs,
                "defaults": ["openpaperwork_gtk.fs.gio"],
            },
            {
                'interface': DocLabels,
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': DocTransactionManager,
                'defaults': ['paperwork_backend.sync'],
            },
            {
                "interface": ImporterFactory,
                "defaults": [
                    'paperwork_backend.docimport.img',
                    'paperwork_backend.docimport.pdf',
                ],
            },
            {
                "interface": Mainloop,
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'import', help=_(
                "Import file(s)"
            )
        )
        p.add_argument(
            '--doc_id', '--doc', '-d', type=str, required=False,
            help=_("Target document for import"),
        )
        p.add_argument(
            '--password', type=str, required=False,
            help=_("PDF password"),
        )
        p.add_argument(
            'files', type=str, nargs='*',
            help=_("Files to import")
        )

    def _file_import_to_dict(self, file_import):
        return {
            "imported": list(file_import.imported_files),
            "ignored": list(file_import.ignored_files),
            "new_docs": list(file_import.new_doc_ids),
            "upd_docs": list(file_import.upd_doc_ids),
            "stats": dict(file_import.stats)
        }

    def cmd_run(self, console, args):
        if args.command != 'import':
            return None

        file_import = paperwork_backend.docimport.FileImport(
            [self.core.call_success(Fs.fs_safe, f) for f in args.files],
            active_doc_id=args.doc_id
        )

        importers = []
        self.core.call_all(ImporterFactory.get_importer, importers, file_import)
        choice = 0

        if len(importers) <= 0:
            console.print(
                _("Don't know how to import file(s) %s") % args.files
            )
            LOGGER.warning("Don't know how to import file(s) %s", args.files)
            return self._file_import_to_dict(file_import)

        if len(importers) > 1:
            console.print(
                _("Found many ways to import file(s) %s.") % args.files
            )
            console.print(
                _("Please select the way you want:")
            )
            choice = -1
            while choice not in range(0, len(importers)):
                for (idx, importer) in enumerate(importers):
                    console.print(f"  {idx + 1} - {importer.get_name()}")
                choice = console.input("? ")
                if choice is None:
                    return self._file_import_to_dict(file_import)
                choice = int(choice) - 1

        importer = importers[choice]
        del importers

        # We must load the labels before importing. Because the label
        # guesser may want to add labels on documents, and therefore
        # we need to know their color
        # TODO(Jflesch): That's slow and overkill. There should be a better
        # way (maybe storing the labels in ~/.local/share/paperwork2 ?)
        console.print(_("Loading labels ..."))
        promises = []
        self.core.call_all(DocLabels.label_load_all, promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        # use transaction_schedule to make sure that document imports
        # are not done before we have loaded the labels
        self.core.call_one(DocTransactionManager.transaction_schedule, promise)

        data = {}
        if args.password is not None:
            data['password'] = args.password

        promise = importer.get_import_promise(data)

        console.print(_("Importing %s ...") % args.files)
        self.core.call_success(
            Mainloop.mainloop_schedule, self.core.call_success,
            DocTransactionManager.transaction_schedule, promise
        )
        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_success(Mainloop.mainloop)
        console.print(rich.text.Text(_("Done")))
        console.print(rich.text.Text(_("Import result:")))
        console.print(rich.text.Text(
            _("- Imported files: %s") % file_import.imported_files
        ))
        console.print(rich.text.Text(
            _("- Non-imported files: %s") % file_import.ignored_files
        ))
        console.print(rich.text.Text(
            _("- New documents: %s") % file_import.new_doc_ids
        ))
        console.print(rich.text.Text(
            _("- Updated documents: %s") % file_import.upd_doc_ids
        ))
        for (k, v) in file_import.stats.items():
            console.print(rich.text.Text(f"- {k}: {v}"))

        return self._file_import_to_dict(file_import)
