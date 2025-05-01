import logging
import os

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.memleak_detector import MemleakDetector
import openpaperwork_core
import openpaperwork_core.deps

from paperwork_backend.interfaces.poppler import Poppler as PopplerInterface


LOGGER = logging.getLogger(__name__)
GI_AVAILABLE = False
GLIB_AVAILABLE = False
POPPLER_AVAILABLE = False


try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError) as exc:
    LOGGER.warning("Failed to import gi", exc_info=exc)

if GI_AVAILABLE:
    try:
        from gi.repository import Gio
        GLIB_AVAILABLE = True
    except (ImportError, ValueError) as exc:
        LOGGER.warning("Failed to import Gio", exc_info=exc)

    try:
        gi.require_version('Poppler', '0.18')
        from gi.repository import Poppler
        POPPLER_AVAILABLE = True
    except (ImportError, ValueError) as exc:
        LOGGER.warning("Failed to import Poppler", exc_info=exc)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    PopplerInterface,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Mainloop,
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                "interface": MemleakDetector,
                "defaults": [],
                "optional": True,
            },
        ]

    def chkdeps(self, out: dict):
        if not GI_AVAILABLE:
            out['gi'] = openpaperwork_core.deps.GI
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not POPPLER_AVAILABLE:
            out['poppler'] = openpaperwork_core.deps.POPPLER

    def poppler_open(self, url, password=None):
        if os.name == "nt":
            # WORKAROUND(Jflesch):
            # Disabled for now on Windows: There is a file descriptor leak
            # somewhere.
            # While it causes little problems on GNU/Linux, on Windows it
            # prevents deleting documents.
            return None

        gio_file = Gio.File.new_for_uri(url)
        doc = self.core.call_one(
            Mainloop.mainloop_execute, Poppler.Document.new_from_gfile,
            gio_file, password=password
        )
        self.core.call_all(MemleakDetector.on_objref_track, doc)
        return doc
