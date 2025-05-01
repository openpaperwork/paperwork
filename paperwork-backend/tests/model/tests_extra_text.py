import unittest

import openpaperwork_core

from paperwork_backend.interfaces.docs import DocExtraText
from paperwork_backend.interfaces.docs import DocText


class TestExtraText(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.model.extra_text")
        self.core.init()

        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_get_boxes(self):
        self.fs.fs = {
            "some_doc": {},
        }

        self.core.call_all(
            DocExtraText.doc_set_extra_text_by_url,
            "file:///some_doc", "some\ntext"
        )

        text = []
        self.core.call_all(
            DocText.doc_get_text_by_url, text, "file:///some_doc"
        )
        self.assertEqual(text, ['some\ntext'])
