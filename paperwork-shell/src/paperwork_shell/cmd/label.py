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

from openpaperwork_core.cmd.util import ask_confirmation

from .. import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                "interface": "doc_labels",
                "defaults": ["paperwork_backend.model.labels"],
            },
            {
                "interface": "document_storage",
                "defaults": ["paperwork_backend.model.workdir"],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        label_parser = parser.add_parser(
            'label', help=_("Commands to manage labels")
        )
        subcmd_parser = label_parser.add_subparsers(
            help=_("label command"), dest='sub_command', required=True
        )

        subcmd_parser.add_parser('list')
        p = subcmd_parser.add_parser('show')
        p.add_argument(
            'doc_ids', nargs='*', default=[],
            help=_("Target documents")
        )

        p = subcmd_parser.add_parser('add')
        p.add_argument('doc_id', help=_("Target document"))
        p.add_argument('label_name', help=_("Label to add"))
        p.add_argument(
            '--color', '-c', default=None,
            help=_("Label color (ex: '#aa22cc')"), required=False
        )

        p = subcmd_parser.add_parser('remove')
        p.add_argument('doc_id', help=_("Target document"))
        p.add_argument('label_name', help=_("Label to remove"))

        p = subcmd_parser.add_parser('delete')
        p.add_argument(
            'label_name', help=_("Label to delete from *all* documents")
        )

    def _load_all_labels(self, console):
        console.print(_("Loading all labels ... "))
        promises = []
        self.core.call_all("label_load_all", promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        self.core.call_one("mainloop_schedule", promise.schedule)
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")
        console.print(_("Done"))

    def _upd_doc(self, console, doc_id):
        self.core.call_success("transaction_simple", [("upd", doc_id),])
        self.core.call_success("mainloop_quit_graceful")
        self.core.call_success("mainloop")

    def _show(self, console, doc_ids):
        out = {}
        for doc_id in doc_ids:
            doc_url = self.core.call_success("doc_id_to_url", doc_id)
            labels = set()
            self.core.call_all("doc_get_labels_by_url", labels, doc_url)
            labels = list(labels)
            labels.sort()
            out[doc_id] = labels

            labels_str = self.core.call_success(
                "format_labels", labels, separator=" "
            )
            console.print(f"{doc_id}: {labels_str}")
        return out

    def cmd_run(self, console, args):
        if args.command != 'label':
            return None

        if args.sub_command == 'list':
            self._load_all_labels(console)

            labels = set()
            self.core.call_all("labels_get_all", labels)
            labels = list(labels)
            labels.sort()

            console.print("")
            labels_str = self.core.call_success(
                "format_labels", labels, separator=" "
            )
            console.print(labels_str)
            return labels

        elif args.sub_command == 'show':

            return self._show(console, args.doc_ids)

        elif args.sub_command == "add":

            color = args.color
            if color is not None:
                # make sure the color is valid
                color = self.core.call_success("label_color_to_rgb", color)
                color = self.core.call_success("label_color_from_rgb", color)

            self._load_all_labels(console)
            doc_url = self.core.call_success("doc_id_to_url", args.doc_id)
            self.core.call_success(
                "doc_add_label_by_url", doc_url, args.label_name, color
            )

            self._upd_doc(console, args.doc_id)

            return self._show(console, [args.doc_id])

        elif args.sub_command == "remove":

            doc_url = self.core.call_success("doc_id_to_url", args.doc_id)
            self.core.call_all(
                "doc_remove_label_by_url", doc_url, args.label_name
            )
            self._upd_doc(console, args.doc_id)
            return self._show(console, [args.doc_id])

        elif args.sub_command == "delete":

            label = args.label_name

            r = ask_confirmation(
                console,
                _(
                    "Are you sure you want to delete label '%s' from all"
                    " documents ?"
                ) % label,
                default_interactive='n',
                default_non_interactive='y',
            )
            if r != 'y':
                sys.exit(1)

            all_docs = []
            self.core.call_all("storage_get_all_docs", all_docs)

            updated_docs = []

            for (doc_id, doc_url) in all_docs:
                labels = set()
                self.core.call_all("doc_get_labels_by_url", labels, doc_url)
                labels = {l for (l, c) in labels}
                if label not in labels:
                    continue

                if self.interactive:
                    print("Removing label '{}' from document '{}'".format(
                        label, doc_id
                    ))
                updated_docs.append(doc_id)
                self.core.call_all("doc_remove_label_by_url", doc_url, label)

            if self.interactive:
                sys.stdout.write("Committing changes in index ... ")
                sys.stdout.flush()

            self.core.call_success("transaction_simple", [
                ("upd", doc_id) for doc_id in updated_docs
            ])
            self.core.call_success("mainloop_quit_graceful")
            self.core.call_success("mainloop")

            if self.interactive:
                sys.stdout.write("Done\n")
            return updated_docs

        if self.interactive:
            print("Unknown label command: {}".format(args.sub_command))
        return None
