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
import sys

import openpaperwork_core
import openpaperwork_core.promise

import paperwork_backend.docexport

from . import util
from .. import _


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self, core):
        super().__init__(core)
        self.console = None

    @classmethod
    def get_interfaces(cls):
        return ['shell']

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": "document_storage",
                "defaults": ["paperwork_backend.model.workdir"],
            },
            {
                "interface": "fs",
                "defaults": ["openpaperwork_gtk.fs.gio"],
            },
            {
                "interface": "export_pipes",
                "defaults": [
                    'paperwork_backend.docexport.generic',
                    'paperwork_backend.docexport.img',
                    'paperwork_backend.docexport.pdf',
                    'paperwork_backend.docexport.pillowfight',
                ],
            },
        ]

    def cmd_set_console(self, console):
        self.console = console

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser(
            'export', help=_(
                "Export a document, a page, or a set of pages."
                " Example:"
                " paperwork-cli export 20150303_2314_39 -p 2 -f img_boxes"
                " -f grayscale -f jpeg -o ~/tmp/pouet.jpg"
            )
        )
        p.add_argument('doc_id', help=_('Document to export'))
        p.add_argument(
            '--pages', '-p', type=str, required=False,
            help=_(
                "Pages to export"
                " (single integer, range or comma-separated list,"
                " default: all pages)"
            )
        )
        p.add_argument(
            '--filters', '-f', nargs=1, action='append',
            type=str, required=False,
            help=_(
                "Export filters. Specify this option once for each filter"
                " to apply (ex: '-f grayscale -f jpeg')."
            )
        )
        p.add_argument(
            '--out', '-o', type=str, required=False,
            help=_(
                "Output file/directory. If not specified, will list"
                " the filters that could be chained after those already"
                " specified."
            )
        )

    def _print_possible_pipes(self, next_pipes):
        next_pipes = [pipe.name for pipe in next_pipes]
        next_pipes.sort()
        self.console.print(_("Next possible filters are:"))
        for pipe in next_pipes:
            self.console.print(f"- {pipe}")
        return next_pipes

    @staticmethod
    def _data_type_to_str(dtype):
        if dtype == paperwork_backend.docexport.ExportDataType.DOCUMENT_SET:
            return _("a document list")
        elif dtype == paperwork_backend.docexport.ExportDataType.DOCUMENT:
            return _("a document")
        elif dtype == paperwork_backend.docexport.ExportDataType.PAGE:
            return _("pages")
        elif dtype == paperwork_backend.docexport.ExportDataType.IMG_BOXES:
            return _("Images and text boxes")
        return f"Unknown: {dtype}"

    def _check_pipeline(self, doc_url, pages, filters):
        filters = list(filters)

        next_pipes = []
        if pages is not None and len(pages) > 0:
            self.core.call_all(
                "export_get_pipes_by_page", next_pipes, doc_url, pages[0]
            )
        else:
            self.core.call_all(
                "export_get_pipes_by_doc_url", next_pipes, doc_url
            )
        if len(filters) <= 0:
            self.console.print(_("Need at least one filter."))
            return self._print_possible_pipes(next_pipes)
        if not filters[0] in next_pipes:
            sys.stderr.write(
                _("First filter cannot be '{}'").format(
                    filters[0].name
                ) + "\n"
            )
            self._print_possible_pipes(next_pipes)
            return False

        output_type = None
        while len(filters) > 0:
            f = filters.pop(0)
            if output_type is not None and f.input_type != output_type:
                sys.stderr.write(
                    _(
                        "Filter mismatch:"
                        " {0} expects {1} as input. Got {2} instead"
                    ).format(
                        f.name,
                        self._data_type_to_str(f.input_type),
                        self._data_type_to_str(output_type),
                    ) + "\n"
                )
                return False
            output_type = f.output_type

        expected_output_type = (
            paperwork_backend.docexport.ExportDataType.OUTPUT_URL_FILE
        )
        if output_type != expected_output_type:
            self.console.print(
                _("Last filter will output {}.").format(
                    self._data_type_to_str(output_type)
                ) + "\n"
            )
            next_pipes = []
            self.core.call_all(
                "export_get_pipes_by_input", next_pipes, output_type
            )
            return self._print_possible_pipes(next_pipes)
        return None

    def cmd_run(self, console, args):
        if args.command != 'export':
            return None

        # argument parsing

        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        if doc_url is None:
            sys.stderr.write(f"Document {doc_id} doesn't exist\n")
            return False
        pages = util.parse_page_list(args)
        filters = args.filters if args.filters is not None else []
        out = args.out

        if pages is None or len(pages) <= 0:
            input_value = paperwork_backend.docexport.ExportData.build_doc(
                doc_id, doc_url
            )
        else:
            input_value = paperwork_backend.docexport.ExportData.build_pages(
                doc_id, doc_url, pages
            )

        filters_str = [f[0] for f in filters]
        filters = []
        for f in filters_str:
            p = self.core.call_success('export_get_pipe_by_name', f)
            if p is None:
                sys.stderr.write(
                    (_("Unknown filters: %s") % f) + "\n"
                )
                if len(filters) <= 0:
                    sys.stderr.write(
                        _(
                            "Run the command without any filter to have a list"
                            " of possible filters to start with."
                        ) + "\n"
                    )
                return False
            filters.append(p)

        r = self._check_pipeline(doc_url, pages, filters)
        if r is not None:
            return r

        if out is None or out == "":
            sys.stderr.write(
                _(
                    "Filter list is complete,"
                    " but no output file specified (-o)"
                ) + "\n"
            )
            return []

        # else try to export
        out = self.core.call_success("fs_safe", out)

        def get_input_value():
            return input_value

        promise = openpaperwork_core.promise.Promise(
            self.core, get_input_value
        )
        for pipe in filters:
            promise = promise.then(
                pipe.get_promise(result='final', target_file_url=out)
            )

        self.console.print(_("Exporting to %s ... ") % out)
        self.core.call_one("mainloop_schedule", promise.schedule)
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")
        self.console.print(_("Done") + "\n")
        r = (self.core.call_success("fs_exists", out) is not None)
        if not r:
            sys.stderr.write(_("Export failed !") + "\n")
        return r
