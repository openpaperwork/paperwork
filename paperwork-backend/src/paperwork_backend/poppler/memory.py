import openpaperwork_core
import openpaperwork_core.deps

GI_AVAILABLE = False
GLIB_AVAILABLE = False
POPPLER_AVAILABLE = False


try:
    import gi
    from gi.repository import GLib
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass


if GI_AVAILABLE:
    try:
        from gi.repository import Gio
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        gi.require_version('Poppler', '0.18')
        from gi.repository import Poppler
        POPPLER_AVAILABLE = True
    except (ImportError, ValueError):
        pass


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'poppler',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GI_AVAILABLE:
            out['gi'] = openpaperwork_core.deps.GI
        if not GLIB_AVAILABLE:
            out['glib'] = openpaperwork_core.deps.GLIB
        if not POPPLER_AVAILABLE:
            out['poppler'] = openpaperwork_core.deps.POPPLER

    def poppler_open(self, url, password=None):
        # Poppler.Document.new_from_data() expects .. a string
        # Poppler.Document.new_from_bytes() only exist starting with 0.82
        with self.core.call_success("fs_open", url, "rb") as fd:
            data = fd.read()
        ldata = len(data)
        data = GLib.Bytes.new(data)
        # Gio.MemoryInputStream.new_from_data() may leak
        # https://stackoverflow.com/questions/45838863/gio-memoryinputstream
        # --> use Gio.MemoryInputStream.new_from_bytes() instead
        data = Gio.MemoryInputStream.new_from_bytes(data)
        self.core.call_all("on_objref_track", data)
        doc = self.core.call_one(
            "mainloop_execute", Poppler.Document.new_from_stream,
            data, ldata, password=password
        )
        return doc
