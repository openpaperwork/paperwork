import cairo
import gc
import os
import unittest
import openpaperwork_core

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.memleak_detector import MemleakDetector

from paperwork_backend.interfaces.poppler import Poppler


class TestMemoryDescriptorLeak(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_leak(self):
        self.tracking = False
        self.disposed = False

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(
                openpaperwork_core.PluginBase,
                MemleakDetector,
            ):
                def _on_dispose(s):
                    self.disposed = True

                def on_objref_track(s, obj):
                    self.tracking = True
                    obj.weak_ref(s._on_dispose)

                def on_objref_graph(self):
                    pass

                def on_memleak_track_stop(self):
                    pass


        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.python")
        self.core.load("paperwork_backend.poppler.memory")
        self.core.load("fake_module", FakeModule())

        self.core.init()

        self.simple_doc_url = self.core.call_success(
            Fs.fs_safe,
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_doc.pdf"
            )
        )

        gc.collect()
        gc.collect()

        doc = self.core.call_success(Poppler.poppler_open, self.simple_doc_url)
        self.assertIsNotNone(doc)

        self.assertTrue(self.tracking)
        self.assertFalse(self.disposed)

        page = doc.get_page(0)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        ctx = cairo.Context(surface)
        page.render(ctx)

        self.assertFalse(self.disposed)

        page = None
        doc = None
        gc.collect()
        gc.collect()

        self.assertTrue(self.disposed)
