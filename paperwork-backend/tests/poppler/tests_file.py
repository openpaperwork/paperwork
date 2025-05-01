import cairo
import gc
import os
import psutil
import unittest

from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core

from paperwork_backend.interfaces.poppler import Poppler


class TestFileDescriptorLeak(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_fd_leak(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.python")
        self.core.load("paperwork_backend.poppler.file")
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

        current_fds = list(psutil.Process().open_files())

        doc = self.core.call_success(Poppler.poppler_open, self.simple_doc_url)
        self.assertIsNotNone(doc)

        new_fds = list(psutil.Process().open_files())
        self.assertNotEqual(len(current_fds), len(new_fds))

        doc = None
        gc.collect()
        gc.collect()

        new_fds = list(psutil.Process().open_files())
        self.assertEqual(len(current_fds), len(new_fds))

    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_fd_leak2(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.python")
        self.core.load("paperwork_backend.poppler.file")
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

        current_fds = list(psutil.Process().open_files())

        doc = self.core.call_success(Poppler.poppler_open, self.simple_doc_url)
        self.assertIsNotNone(doc)
        page = doc.get_page(0)

        new_fds = list(psutil.Process().open_files())
        self.assertNotEqual(len(current_fds), len(new_fds))

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        ctx = cairo.Context(surface)
        page.render(ctx)

        new_fds = list(psutil.Process().open_files())
        self.assertNotEqual(len(current_fds), len(new_fds))

        page = None
        doc = None
        gc.collect()
        gc.collect()

        new_fds = list(psutil.Process().open_files())
        self.assertEqual(len(current_fds), len(new_fds))
