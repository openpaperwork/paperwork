import re
import unittest

import openpaperwork_core

from paperwork_backend.interfaces.pages import PageText


TEST_XML = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
 "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <title>OCR output</title>
</head>
<body>
<p>
    <span class="ocr_line" title="bbox 10 20 30 40">
        <span class="ocrx_word" title="bbox 1 2 3 4">ABC</span>
        <span class="ocrx_word" title="bbox 5 6 7 8">def</span>
    </span>
</p>
</body>
</html>
"""


class TestHocr(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.model.hocr")
        self.core.init()

        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_get_boxes(self):
        self.fs.fs = {
            "some_doc": {
                "paper.4.words": TEST_XML,
            },
        }

        lines = self.core.call_success(
            PageText.page_get_boxes_by_url, "file:///some_doc", 1
        )
        self.assertIsNone(lines)
        lines = list(
            self.core.call_success(
                PageText.page_get_boxes_by_url, "file:///some_doc", 3
            )
        )
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].position, ((10, 20), (30, 40)))
        self.assertEqual(len(lines[0].word_boxes), 2)
        self.assertEqual(lines[0].word_boxes[0].position, ((1, 2), (3, 4)))
        self.assertEqual(lines[0].word_boxes[0].content, "ABC")
        self.assertEqual(lines[0].word_boxes[1].position, ((5, 6), (7, 8)))
        self.assertEqual(lines[0].word_boxes[1].content, "def")

    def test_get_text(self):
        self.fs.fs = {
            "some_doc": {
                "paper.4.words": TEST_XML,
            },
        }

        lines = self.core.call_success(
            PageText.page_get_text_by_url, "file:///some_doc", 1
        )
        self.assertIsNone(lines)
        txt = self.core.call_success(
            PageText.page_get_text_by_url, "file:///some_doc", 3
        ).replace("\n", " ")
        txt = re.sub(" +", " ", txt)
        txt = txt.strip()
        self.assertEqual(txt, "ABC def")

    def test_has_text(self):
        self.fs.fs = {
            "some_doc": {
                "paper.4.words": TEST_XML,
            },
        }

        self.assertIsNone(self.core.call_success(
            PageText.page_has_text_by_url, "file:///some_doc", 1
        ))
        self.assertTrue(self.core.call_success(
            PageText.page_get_text_by_url, "file:///some_doc", 3
        ))
        self.core.call_all(
            PageText.page_set_boxes_by_url, "file:///some_doc", 3, []
        )
        self.assertFalse(self.core.call_success(
            PageText.page_has_text_by_url, "file:///some_doc", 3
        ))
