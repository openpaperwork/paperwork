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
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.docs import DocExtraText

from paperwork_shell import _


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=["paperwork_backend.model.workdir"],
            ),
            openpaperwork_core.Dependency(
                interface=DocExtraText,
                defaults=['paperwork_backend.model.extra_text'],
            ),
        ]

    def cmd_complete_argparse(self, parser):
        extra_text_parser = parser.add_parser(
            'extra_text', help=_(
                "Manage additional text attached to documents"
            )
        )

        subparser = extra_text_parser.add_subparsers(
            help=_('sub-command'), dest='subcommand', required=True
        )

        parser = subparser.add_parser(
            'get', help=_("Get a document additional text")
        )
        parser.add_argument('doc_id')

        parser = subparser.add_parser(
            'set', help=_("Set a document additional text")
        )
        parser.add_argument('doc_id')
        parser.add_argument('text')

    def cmd_run(self, console, args):
        if args.command != 'extra_text':
            return None
        doc_id = args.doc_id
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)
        if args.subcommand == "get":
            return self._cmd_get(console, doc_id, doc_url)
        elif args.subcommand == "set":
            return self._cmd_set(console, doc_id, doc_url, args.text)
        else:
            return None

    def _cmd_get(self, console, doc_id, doc_url):
        text = []
        self.core.call_success(DocExtraText.doc_get_extra_text_by_url, text, doc_url)
        if len(text) > 0:
            console.print("  " + _("Additional text:"))
            console.print("\n".join(text))
        else:
            console.print(_("No additional text"))
        return text

    def _cmd_set(self, console, doc_id, doc_url, text):
        text = text.strip()
        self.core.call_success(DocExtraText.doc_set_extra_text_by_url, doc_url, text)
        console.print(_("Done"))
        return True
