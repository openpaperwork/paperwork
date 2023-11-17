import logging


GI_AVAILABLE = False
GTK_AVAILABLE = False


try:
    import gi
    from gi.repository import Gio
    from gi.repository import GLib
    GI_AVAILABLE = True
except (ValueError, ImportError):
    pass

if GI_AVAILABLE:
    try:
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        GTK_AVAILABLE = True
    except (ImportError, ValueError):
        pass


import openpaperwork_core  # noqa: E402
import openpaperwork_core.deps  # noqa: E402

from . import deps  # noqa: E402


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.activated = False
        self.app = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_init',
        ]

    def init(self, core):
        super().init(core)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
            out['gtk'].update(deps.GTK)

    def gtk_init(self, main_func, *args):
        if hasattr(GLib, 'set_application_name'):
            GLib.set_application_name("Paperwork")
        GLib.set_prgname("work.openpaper.Paperwork")

        self.app = Gtk.Application(
            application_id="work.openpaper.Paperwork",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE |
            Gio.ApplicationFlags.HANDLES_OPEN
        )
        self.app.connect("handle-local-options", main_func, *args)
        self.app.connect("activate", self._on_activate)
        self.app.connect("open", self._on_open)
        Gtk.Application.set_default(self.app)
        self.app.register()
        # self.app.run(in_args)
        self.app.run()

    def on_quit(self):
        if self.app is not None:
            self.app.quit()

    def gtk_get_app(self):
        return self.app

    # called when paperwork is launched without a file to import as argument.
    # when a second instance of paperwork is run, this is called in the main
    # instance instead.
    def _on_activate(self, _app):
        if not self.activated:
            self.activated = True
            self.core.call_all("on_gtk_initialized")

            LOGGER.info("Ready")
            self.core.call_one("mainloop", halt_on_uncaught_exception=False)
            LOGGER.info("Quitting")
            self.core.call_all("config_save")
            self.core.call_all("on_quit")
        else:
            # a second instance was activated, we are the main one
            self.core.call_all("mainwindow_present")

    # called when paperwork is launched with files to import as argument.
    # when a second instance of paperwork is run, this is called in the main
    # instance instead.
    def _on_open(self, app, files, _count, _hint):
        uris = [file.get_uri() for file in files]
        self.core.call_one(
            "mainloop_schedule",
            self.core.call_all, "gtk_doc_import", uris
        )
        # either start paperwork if we are the main instance, or focus it if
        # this signal is raised remotely
        self._on_activate(app)
