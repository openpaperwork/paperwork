import os
import shutil
import tempfile
import unittest

import openpaperwork_core


class TestHocr(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.model.pdf")
        self.core.init()

        self.simple_doc_url = self.core.call_success(
            "fs_safe",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "simple_doc.pdf"
            )
        )
        self.full_doc_url = self.core.call_success(
            "fs_safe",
            os.path.dirname(os.path.abspath(__file__))
        )

        mapping = self.full_doc_url + "/page_map.csv"
        if self.core.call_success("fs_exists", mapping):
            self.core.call_success("fs_unlink", mapping, trash=False)

    def tearDown(self):
        mapping = self.full_doc_url + "/page_map.csv"
        if self.core.call_success("fs_exists", mapping):
            self.core.call_success("fs_unlink", mapping, trash=False)

    def test_is_doc(self):
        self.assertTrue(self.core.call_success("is_doc", self.simple_doc_url))
        self.assertTrue(self.core.call_success("is_doc", self.full_doc_url))

    def test_hash(self):
        h = self.core.call_success("doc_get_hash_by_url", self.simple_doc_url)
        expected = (
            0x7d2ffb0e8ddce8f7dfbb4a8dfc14d563b272bd47b1bafb9617fbfd228bf2eecd
        )
        self.assertEqual(h, expected)

    def test_get_nb_pages(self):
        self.assertEqual(
            self.core.call_success(
                "doc_get_nb_pages_by_url", self.simple_doc_url
            ), 1
        )

        self.assertEqual(
            self.core.call_success(
                "doc_get_nb_pages_by_url", self.full_doc_url
            ), 4
        )

        self.core.call_all("page_delete_by_url", self.full_doc_url, 2)
        self.assertEqual(
            self.core.call_success(
                "doc_get_nb_pages_by_url", self.full_doc_url
            ), 3
        )

    def test_get_text(self):
        text = []
        self.core.call_all("doc_get_text_by_url", text, self.simple_doc_url)
        self.assertEqual(text, [
            'This is a test PDF file.\n'
            'Written by Jflesch.'
        ])

    def test_get_boxes(self):
        lines = list(self.core.call_success(
            "page_get_boxes_by_url", self.simple_doc_url, 0
        ))

        self.assertEqual(len(lines), 2)

        self.assertEqual(lines[0].position, ((227, 228), (656, 281)))
        self.assertEqual(len(lines[0].word_boxes), 6)
        self.assertEqual(lines[0].content, "This is a test PDF file.")
        self.assertEqual(
            lines[0].word_boxes[0].position, ((227, 228), (312, 281))
        )
        self.assertEqual(lines[0].word_boxes[0].content, "This")
        self.assertEqual(
            lines[0].word_boxes[1].position, ((324, 228), (356, 281))
        )
        self.assertEqual(lines[0].word_boxes[1].content, "is")
        self.assertEqual(
            lines[0].word_boxes[2].position, ((368, 228), (389, 281))
        )
        self.assertEqual(lines[0].word_boxes[2].content, "a")
        self.assertEqual(
            lines[0].word_boxes[3].position, ((401, 228), (468, 281))
        )
        self.assertEqual(lines[0].word_boxes[3].content, "test")
        self.assertEqual(
            lines[0].word_boxes[4].position, ((480, 228), (568, 281))
        )
        self.assertEqual(lines[0].word_boxes[4].content, "PDF")
        self.assertEqual(
            lines[0].word_boxes[5].position, ((580, 228), (656, 281))
        )
        self.assertEqual(lines[0].word_boxes[5].content, "file.")

        self.assertEqual(lines[1].position, ((227, 284), (588, 337)))
        self.assertEqual(lines[1].content, "Written by Jflesch.")
        self.assertEqual(len(lines[1].word_boxes), 3)
        self.assertEqual(
            lines[1].word_boxes[0].position, ((227, 284), (371, 337))
        )
        self.assertEqual(lines[1].word_boxes[0].content, "Written")
        self.assertEqual(
            lines[1].word_boxes[1].position, ((383, 284), (431, 337))
        )
        self.assertEqual(lines[1].word_boxes[1].content, "by")
        self.assertEqual(
            lines[1].word_boxes[2].position, ((443, 284), (588, 337))
        )
        self.assertEqual(lines[1].word_boxes[2].content, "Jflesch.")


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.model.pdf")
        self.core.init()

        self.pdf = self.core.call_success(
            "fs_safe",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "doc.pdf"
            )
        )

        self.work_dir = tempfile.mkdtemp(prefix="paperwork_tests_all_")
        self.work_dir_url = self.core.call_success("fs_safe", self.work_dir)
        self.doc_url = self.core.call_success(
            "fs_join", self.work_dir_url, "20200525_1241_05"
        )
        self.core.call_success("fs_mkdir_p", self.doc_url)
        self.core.call_success(
            "fs_copy", self.pdf,
            self.core.call_success("fs_join", self.doc_url, "doc.pdf")
        )
        self.mapping = self.doc_url + "/page_map.csv"

    def tearDown(self):
        shutil.rmtree(self.work_dir)

    def test_crappy_mapping(self):
        with self.core.call_success("fs_open", self.mapping, "w") as fd:
            fd.write("original_page_index,target_page_index\n")
            fd.write("0,-1\n")
            fd.write("1,2\n")
            fd.write("2,-1\n")
            fd.write("3,-1\n")
        self.assertEqual(
            self.core.call_success(
                "doc_get_nb_pages_by_url", self.doc_url
            ), 3
        )
        self.assertIsNotNone(
            self.core.call_success("page_get_img_url", self.doc_url, 0)
        )
        self.assertIsNotNone(
            self.core.call_success("page_get_img_url", self.doc_url, 1)
        )
        self.assertIsNotNone(
            self.core.call_success("page_get_img_url", self.doc_url, 2)
        )
        self.assertIsNone(
            self.core.call_success("page_get_img_url", self.doc_url, 3)
        )


class TestPassword(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.model.pdf")
        self.core.init()

        password_doc_url = self.core.call_success(
            "fs_safe",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_password.pdf"
            )
        )

        self.tmp_doc_dir = tempfile.mkdtemp()
        self.tmp_doc_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            self.tmp_doc_dir
        )

        doc_pdf = self.core.call_success(
            "fs_join", self.tmp_doc_url, "doc.pdf"
        )
        passwd_txt = self.core.call_success(
            "fs_join", self.tmp_doc_url, "passwd.txt"
        )

        self.core.call_all("fs_copy", password_doc_url, doc_pdf)
        with self.core.call_success("fs_open", passwd_txt, "w") as fd:
            fd.write("test1234")

    def tearDown(self):
        shutil.rmtree(self.tmp_doc_dir)

    def test_open_page(self):
        boxes = self.core.call_success(
            "page_get_boxes_by_url", self.tmp_doc_url, 0
        )
        self.assertNotEqual(len(boxes), 0)
        img_url = self.core.call_success(
            "page_get_img_url", self.tmp_doc_url, 0
        )
        self.assertIn("password=", img_url)
