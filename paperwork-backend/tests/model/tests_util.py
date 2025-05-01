import unittest

import openpaperwork_core

from paperwork_backend.interfaces.docs import Docs
import paperwork_backend.model.util


class TestUtil(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.fake")

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(
                openpaperwork_core.PluginBase,
                Docs,
            ):
                def doc_get_nb_pages_by_url(s, doc_url):
                    doc_url = doc_url[len("file:///"):]
                    return len(self.fs.fs[doc_url])

                def doc_get_mtime_by_url(self, doc_url):
                    pass

        self.core.load("fake_module", FakeModule())
        self.core.init()

        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_delete_page_file(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.words": "abcdef",
                "paper.2.words": "ghijkl",
                "paper.3.words": "mnopqr",
                "paper.4.words": "stuvwx",
            },
        }

        r = paperwork_backend.model.util.delete_page_file(
            self.core, "paper.{}.words", "file:///some_doc", 1
        )
        self.assertTrue(r)

        self.assertEqual(
            self.fs.fs,
            {
                "some_doc": {
                    "paper.1.words": "abcdef",
                    "paper.2.words": "mnopqr",
                    "paper.3.words": "stuvwx",
                },
            }
        )

    def test_move_page_file(self):
        self.fs.fs = {
            "source_doc": {
                "paper.1.words": "Aabcdef",
                "paper.2.words": "Aghijkl",
                "paper.3.words": "Amnopqr",
                "paper.4.words": "Astuvwx",
            },
            "dest_doc": {
                "paper.1.words": "Babcdef",
                "paper.2.words": "Bghijkl",
                "paper.3.words": "Bmnopqr",
                "paper.4.words": "Bstuvwx",
            },
        }

        r = paperwork_backend.model.util.move_page_file(
            self.core, "paper.{}.words",
            "file:///source_doc", 2,
            "file:///dest_doc", 1
        )
        self.assertTrue(r)

        self.assertEqual(
            self.fs.fs,
            {
                "source_doc": {
                    "paper.1.words": "Aabcdef",
                    "paper.2.words": "Aghijkl",
                    "paper.3.words": "Astuvwx",
                },
                "dest_doc": {
                    "paper.1.words": "Babcdef",
                    "paper.2.words": "Amnopqr",
                    "paper.3.words": "Bghijkl",
                    "paper.4.words": "Bmnopqr",
                    "paper.5.words": "Bstuvwx",
                },
            }
        )

    def test_move_page_file_same_doc(self):
        self.fs.fs = {
            "source_doc": {
                "paper.1.words": "Aabcdef",
                "paper.2.words": "Aghijkl",
                "paper.3.words": "Amnopqr",
                "paper.4.words": "Astuvwx",
            },
        }

        r = paperwork_backend.model.util.move_page_file(
            self.core, "paper.{}.words",
            "file:///source_doc", 2,
            "file:///source_doc", 1
        )
        self.assertTrue(r)

        self.assertEqual(
            self.fs.fs,
            {
                "source_doc": {
                    "paper.1.words": "Aabcdef",
                    "paper.2.words": "Amnopqr",
                    "paper.3.words": "Aghijkl",
                    "paper.4.words": "Astuvwx",
                },
            }
        )
