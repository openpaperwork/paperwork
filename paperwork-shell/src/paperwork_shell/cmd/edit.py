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
import sys

import rich.text

import openpaperwork_core

import paperwork_backend.pageedit

from . import util
from .. import _


LOGGER = logging.getLogger(__name__)


class NullUI(paperwork_backend.pageedit.AbstractPageEditorUI):
    def __init__(self):
        super().__init__()


class CliUI(paperwork_backend.pageedit.AbstractPageEditorUI):
    def __init__(self, core, console):
        super().__init__()
        self.core = core
        self.console = console

    def show_preview(self, img):
        terminal_width = shutil.get_terminal_size()[0] - 1
        img = self.core.call_success(
            "img_render", img, terminal_width=terminal_width
        )
        if img is None:
            return
        for line in img:
            self.console.print(rich.text.Text.from_ansi(line))
        self.console.print("")


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            # optional dependency
            # {
            #     "interface": "img_renderer",
            #     "defaults": ["paperwork_shell.display.docrendering.img"],
            # },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                "interface": "page_editor",
                "defaults": ["paperwork_backend.pageedit.pageeditor"],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        # just so we can get the modifier list
        editor = self.core.call_success("page_editor_get", None, 0, NullUI())
        modifiers = editor.get_modifiers()

        modifiers = [
            modifier['id']
            for modifier in modifiers
            if not modifier['need_frame']
        ]

        edit_parser = parser.add_parser('edit', help=_("Edit page"))
        edit_parser.add_argument(
            '--modifiers', '-m', type=str, required=True,
            help=_(
                "List of image modifiers (comma separated, possible values:"
                " {})"
            ).format(modifiers)
        )
        # we need page number(s), but for consistency with other commands,
        # we require this argument as an option like '--opt' instead of
        # a positional argument.
        edit_parser.add_argument('--pages', '-p', type=str, required=True)
        edit_parser.add_argument('doc_id')

    def cmd_run(self, console, args):
        if args.command != 'edit':
            return None
        doc_id = args.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        pages = util.parse_page_list(args)
        modifiers = args.modifiers.split(",")
        out = []

        for page_idx in pages:
            out.append((doc_id, page_idx))
            console.print(
                _("Modifying document {} page {} ...").format(
                    doc_id, page_idx
                )
            )
            console.print(_("Original:"))
            ui = CliUI(self.core, console)

            page_editor = self.core.call_success(
                "page_editor_get", doc_url, page_idx, ui
            )

            promise = openpaperwork_core.promise.Promise(self.core)
            for modifier in modifiers:
                promise = promise.then(console.print, f"{modifier}:")
                promise = promise.then(
                    page_editor.on_modifier_selected(modifier)
                )

            if promise is not None:
                promise = promise.then(
                    sys.stdout.write,
                    _("Generating in high quality and saving ...") + " "
                )
                promise = promise.then(
                    lambda *args, **kwargs: sys.stdout.flush()
                )
                promise = promise.then(page_editor.on_save())
                promise = promise.then(console.print, "Done")

                def on_err(exc):
                    LOGGER.error(
                        "Edition of %s p%d failed",
                        doc_id, page_idx,
                        exc_info=exc
                    )
                    page_editor.on_cancel()
                    raise exc

                promise.catch(on_err)

                promise.schedule()

                self.core.call_all("mainloop_quit_graceful")
                self.core.call_one("mainloop")

        console.print(_("Committing ...") + " ")

        self.core.call_success("transaction_simple", [("upd", doc_id),])
        self.core.call_success("mainloop_quit_graceful")
        self.core.call_success("mainloop")

        console.print(_("Done"))
        console.print(_("All done !"))

        return out
