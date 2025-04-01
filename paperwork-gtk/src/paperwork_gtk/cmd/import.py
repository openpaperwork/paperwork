import logging

try:
    from gi.repository import Gio
    HAS_GTK_GLIB = True
except (ImportError, ValueError):
    HAS_GTK_GLIB = False

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
            {
                'interface': 'gtk_doc_import',
                'defaults': ['paperwork_gtk.docimport'],
            },
            {
                'interface': 'gtk_init',
                'defaults': ['openpaperwork_gtk.gtk_init'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser('import', help=_(
            "Run Paperwork and import files passed as arguments into a new "
            "document"
        ))
        p.add_argument("files", metavar="URLS", type=str, nargs="*", help=_(
            "URLs or paths of files to import"
        ))

    def cmd_run(self, console, args):
        if args.command != 'import':
            return None
        if not HAS_GTK_GLIB:
            LOGGER.error("Cannot import file without gtk and glib")
            return None
        self.core.call_all("gtk_init", self._cmd_run, args)

    def _cmd_run(self, app, options, args):
        app = self.core.call_success("gtk_get_app")

        # when no file is specified, we still start the GUI, because the
        # desktop file always calls paperwork-gtk import (see install.py for
        # the rationale).
        if args.files:
            files = [self.core.call_success("fs_safe", f) for f in args.files]
            giofiles = [Gio.File.new_for_uri(f) for f in files]
            LOGGER.info("Will import files %s", " ".join(files))
            if app.get_is_remote():
                LOGGER.info("Passing control to main paperwork instance")
            # open the files, possibly in another process
            app.open(giofiles, "")
        else:
            # possibly in another process
            if app.get_is_remote():
                LOGGER.info("Passing control to main paperwork instance")
            app.activate()
        return 0
