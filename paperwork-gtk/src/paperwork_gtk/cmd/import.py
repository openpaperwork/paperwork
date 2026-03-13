import logging

try:
    from gi.repository import Gio
    HAS_GTK_GLIB = True
except (ImportError, ValueError):
    HAS_GTK_GLIB = False

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkApp, GtkInit

from paperwork_gtk.interfaces.doc_import import DocImport
from paperwork_gtk import _


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Shell,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=DocImport,
                defaults=['paperwork_gtk.docimport'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=["openpaperwork_gtk.fs.gio"],
            ),
            openpaperwork_core.Dependency(
                interface=GtkApp,
                defaults=['openpaperwork_gtk.gtk_init'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkInit,
                defaults=['openpaperwork_gtk.gtk_init'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=['openpaperwork_gtk.mainloop.glib'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=['openpaperwork_gtk.fs.gio'],
            ),
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
        self.core.call_all(GtkInit.gtk_init, self._cmd_run, args)

    def _cmd_run(self, app, options, args):
        app = self.core.call_success(GtkApp.gtk_get_app)

        # when no file is specified, we still start the GUI, because the
        # desktop file always calls paperwork-gtk import (see install.py for
        # the rationale).
        if args.files:
            files = [self.core.call_success(Fs.fs_safe, f) for f in args.files]
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
