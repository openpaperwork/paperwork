import itertools
import os
import shutil
import tempfile
import unittest

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core
import openpaperwork_core.fs

from paperwork_backend.interfaces.docs import Docs
from paperwork_backend.interfaces.pages import PageImg
from paperwork_backend.interfaces.pages import PageManagement
from paperwork_backend.interfaces.pages import Pages


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.int_generator = itertools.count()

        self.pdf = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "doc.pdf"
            )
        )

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model")
        self.core.load("paperwork_backend.model.extra_text")
        self.core.load("paperwork_backend.model.hocr")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.img_overlay")
        self.core.load("paperwork_backend.model.pdf")
        self.core.load("paperwork_backend.model.workdir")
        self.core.init()

        self.work_dir = tempfile.mkdtemp(prefix="paperwork_tests_all_")
        self.work_dir_url = self.core.call_success(Fs.fs_safe, self.work_dir)
        self.core.call_all(Config.config_put, "workdir", self.work_dir_url)

    def tearDown(self):
        shutil.rmtree(self.work_dir)

    def _copy_pdf(self, out_pdf_url):
        dirname = self.core.call_success(Fs.fs_dirname, out_pdf_url)
        self.core.call_success(Fs.fs_mkdir_p, dirname)
        self.core.call_success(Fs.fs_copy, self.pdf, out_pdf_url)

    def _make_file(self, out_file_url):
        dirname = self.core.call_success(Fs.fs_dirname, out_file_url)
        self.core.call_success(Fs.fs_mkdir_p, dirname)
        with self.core.call_success(Fs.fs_open, out_file_url, 'w') as fd:
            fd.write("Generated content {}\n".format(next(self.int_generator)))


class TestAll(BaseTest):
    def setUp(self):
        super().setUp()

        self.doc_pdf = self.core.call_success(
            Fs.fs_join, self.work_dir_url, "20200525_1241_05"
        )
        self._copy_pdf(self.doc_pdf + "/doc.pdf")
        self._make_file(self.doc_pdf + "/paper.2.edited.jpg")
        self._make_file(self.doc_pdf + "/paper.2.words")
        self._make_file(self.doc_pdf + "/extra.txt")

        self.doc_b = self.core.call_success(
            Fs.fs_join, self.work_dir_url, "19851212_1233_00"
        )
        self._make_file(self.doc_b + "/paper.1.jpg")
        self._make_file(self.doc_b + "/paper.1.words")
        self._make_file(self.doc_b + "/paper.2.jpg")
        self._make_file(self.doc_b + "/paper.2.words")
        self._make_file(self.doc_b + "/paper.3.jpg")
        self._make_file(self.doc_b + "/paper.3.words")
        self._make_file(self.doc_b + "/paper.3.edited.jgg")
        self._make_file(self.doc_b + "/paper.4.jpg")
        self._make_file(self.doc_b + "/paper.4.words")

        self.doc_c = self.core.call_success(
            Fs.fs_join, self.work_dir_url, "19851224_1233_00"
        )
        self._make_file(self.doc_c + "/paper.1.jpg")
        self._make_file(self.doc_c + "/paper.1.words")
        self._make_file(self.doc_c + "/paper.2.jpg")
        self._make_file(self.doc_c + "/paper.2.words")
        self._make_file(self.doc_b + "/paper.2.edited.jgg")
        self._make_file(self.doc_c + "/paper.3.jpg")
        self._make_file(self.doc_c + "/paper.3.words")

    def test_basic_nb_pages(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 4)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 3)

    def _get_page_hash(self, doc_url, page_idx):
        return self.core.call_success(
            Pages.page_get_hash_by_url, doc_url, page_idx
        )

    def test_img_page_delete(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]

        self.core.call_all(PageManagement.page_delete_by_url, self.doc_b, 2)

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 3)
        new_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 3)
        ]
        self.assertEqual(hashes[0], new_hashes[0])
        self.assertEqual(hashes[1], new_hashes[1])
        self.assertEqual(hashes[3], new_hashes[2])

    def test_img_page_move_internal(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]

        # 0 becomes 2
        # --> 1 becomes 0
        # --> 2 becomes 1
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_b, 0,
            self.doc_b, 2
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 4)
        new_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertEqual(hashes[0], new_hashes[2])
        self.assertEqual(hashes[1], new_hashes[0])
        self.assertEqual(hashes[2], new_hashes[1])
        self.assertEqual(hashes[3], new_hashes[3])

    def test_img_page_move_internal_reversed(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]

        # 2 becomes 0
        # --> 0 becomes 1
        # --> 1 becomes 2
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_b, 2,
            self.doc_b, 0
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 4)
        new_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertEqual(hashes[0], new_hashes[1])
        self.assertEqual(hashes[1], new_hashes[2])
        self.assertEqual(hashes[2], new_hashes[0])
        self.assertEqual(hashes[3], new_hashes[3])

    def test_img_page_move_external(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 4)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 3)
        doc_b_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]
        doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 3)
        ]

        # doc_c p1 becomes doc_b p2
        # --> doc_c p2 becomes doc_c p1
        # --> doc_b p2 becomes doc_b p3
        # --> doc_b p3 becomes doc_b p4
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_c, 1,
            self.doc_b, 2
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 5)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 2)
        new_doc_b_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 5)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 2)
        ]
        self.assertEqual(doc_b_hashes[0], new_doc_b_hashes[0])
        self.assertEqual(doc_b_hashes[1], new_doc_b_hashes[1])
        self.assertEqual(doc_b_hashes[2], new_doc_b_hashes[3])
        self.assertEqual(doc_b_hashes[3], new_doc_b_hashes[4])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertEqual(doc_c_hashes[1], new_doc_b_hashes[2])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[1])

    def test_pdf_hashes(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]

        # just make sure all the hashes are different from one another
        for (e, h) in enumerate(hashes):
            for i in hashes[e + 1:]:
                self.assertNotEqual(h, i)

    def test_pdf_page_delete(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=4"))

        self.core.call_all(PageManagement.page_delete_by_url, self.doc_pdf, 2)

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 3)
        new_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 3)
        ]

        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/doc.pdf#page=4"))
        self.assertEqual(hashes[0], new_hashes[0])
        self.assertEqual(hashes[1], new_hashes[1])
        self.assertEqual(hashes[3], new_hashes[2])

    def test_pdf_page_move_internal(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]

        # 0 becomes 2
        # --> 1 becomes 0
        # --> 2 becomes 1
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_pdf, 0,
            self.doc_pdf, 2
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        new_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertEqual(hashes[0], new_hashes[2])
        self.assertEqual(hashes[1], new_hashes[0])
        self.assertEqual(hashes[2], new_hashes[1])
        self.assertEqual(hashes[3], new_hashes[3])

    def test_pdf_page_move_internal_reversed(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]

        # 2 becomes 0
        # --> 0 becomes 1
        # --> 1 becomes 2
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_pdf, 2,
            self.doc_pdf, 0
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        new_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertEqual(hashes[0], new_hashes[1])
        self.assertEqual(hashes[1], new_hashes[2])
        self.assertEqual(hashes[2], new_hashes[0])
        self.assertEqual(hashes[3], new_hashes[3])

    def test_img_to_pdf_page_move_then_delete(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 3)
        doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 3)
        ]

        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=4"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 0
        ).endswith("19851224_1233_00/paper.1.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 1
        ).endswith("19851224_1233_00/paper.2.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 2
        ).endswith("19851224_1233_00/paper.3.jpg"))

        # doc_c p1 becomes doc_pdf p2
        # --> doc_c p2 becomes doc_c p1
        # --> doc_pdf p2 becomes doc_pdf p3
        # --> doc_pdf p3 becomes doc_pdf p4
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_c, 1,
            self.doc_pdf, 2
        )
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 5)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 2)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 5)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 2)
        ]
        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[3])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[4])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertEqual(doc_c_hashes[1], new_doc_pdf_hashes[2])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[1])

        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/paper.3.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 4
        ).endswith("20200525_1241_05/doc.pdf#page=4"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 0
        ).endswith("19851224_1233_00/paper.1.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 1
        ).endswith("19851224_1233_00/paper.2.jpg"))

        # we delete the added img page
        self.core.call_all(PageManagement.page_delete_by_url, self.doc_pdf, 2)

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 2)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 2)
        ]
        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[2])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[3])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[1])

        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=4"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 0
        ).endswith("19851224_1233_00/paper.1.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 1
        ).endswith("19851224_1233_00/paper.2.jpg"))

    def test_pdf_to_img_page_move(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 3)
        doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 3)
        ]

        # doc_pdf p3 becomes doc_c p2
        # --> doc_c p2 becomes doc_c p3
        # --> doc_c p2 becomes doc_c p3
        # --> doc_pdf p4 becomes doc_pdf p3
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_pdf, 2,
            self.doc_c, 1
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 3)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 4)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 3)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 4)
        ]

        # in that case, an image page has been generated from the PDF page
        # --> hash of the new image page won't match the PDF hash

        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[1])
        self.assertNotEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[2])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[2])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertNotEqual(doc_c_hashes[1], new_doc_c_hashes[1])
        self.assertEqual(doc_c_hashes[1], new_doc_c_hashes[2])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[3])

    def test_img_to_pdf_complex(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 3)
        doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 3)
        ]

        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=4"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 0
        ).endswith("19851224_1233_00/paper.1.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 1
        ).endswith("19851224_1233_00/paper.2.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 2
        ).endswith("19851224_1233_00/paper.3.jpg"))

        # doc_c p1 becomes doc_pdf p5
        # --> doc_c p2 becomes doc_c p1
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_c, 1,
            self.doc_pdf, 4
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 5)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 2)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 5)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 2)
        ]

        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[2])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[3])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertEqual(doc_c_hashes[1], new_doc_pdf_hashes[4])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[1])

        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=4"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 4
        ).endswith("20200525_1241_05/paper.5.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 0
        ).endswith("19851224_1233_00/paper.1.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 1
        ).endswith("19851224_1233_00/paper.2.jpg"))

        # doc_pdf p5 (previously doc_c p2) becomes doc_pdf p2
        # --> pdf_pdf pages shift
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_pdf, 4,
            self.doc_pdf, 1
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 5)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertEqual(nb, 2)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 5)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 2)
        ]

        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_c_hashes[1], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[2])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[3])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[4])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[1])

        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/paper.3.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 4
        ).endswith("20200525_1241_05/doc.pdf#page=4"))

        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 0
        ).endswith("19851224_1233_00/paper.1.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_c, 1
        ).endswith("19851224_1233_00/paper.2.jpg"))

        # kill doc_c by remove its last 2 pages
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_c, 0,
            self.doc_pdf, 5
        )
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_c, 0,
            self.doc_pdf, 6
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 7)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertIsNone(nb)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 7)
        ]

        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_c_hashes[1], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[2])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[3])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[4])
        self.assertEqual(doc_c_hashes[0], new_doc_pdf_hashes[5])
        self.assertEqual(doc_c_hashes[2], new_doc_pdf_hashes[6])

        # remove a page in the PDF, just for fun
        self.core.call_all(PageManagement.page_delete_by_url, self.doc_pdf, 2)

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 6)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertIsNone(nb)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 6)
        ]

        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_c_hashes[1], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[2])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[3])
        self.assertEqual(doc_c_hashes[0], new_doc_pdf_hashes[4])
        self.assertEqual(doc_c_hashes[2], new_doc_pdf_hashes[5])

        # remove another page in the PDF, just for fun
        self.core.call_all(PageManagement.page_delete_by_url, self.doc_pdf, 1)

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_pdf)
        self.assertEqual(nb, 5)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_c)
        self.assertIsNone(nb)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 5)
        ]

        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[2])
        self.assertEqual(doc_c_hashes[0], new_doc_pdf_hashes[3])
        self.assertEqual(doc_c_hashes[2], new_doc_pdf_hashes[4])

    def test_img_page_move_new_doc(self):
        self.new_doc = self.core.call_success(
            Fs.fs_join, self.work_dir_url, "19871224_1233_00"
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 4)
        doc_b_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_b, 1,
            self.new_doc, 0
        )

        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 3)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.new_doc)
        self.assertEqual(nb, 1)
        new_doc_b_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 3)
        ]
        new_doc_hash = self._get_page_hash(self.new_doc, 0)
        self.assertEqual(doc_b_hashes[0], new_doc_b_hashes[0])
        self.assertEqual(doc_b_hashes[2], new_doc_b_hashes[1])
        self.assertEqual(doc_b_hashes[3], new_doc_b_hashes[2])

        self.assertEqual(doc_b_hashes[1], new_doc_hash)

    def test_img_in_pdf_move(self):
        # Bug report #245 on openpaper.work

        # JPEG goes at the end of the PDF
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_b, 1,
            self.doc_pdf, 4
        )
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=4"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 4
        ).endswith("20200525_1241_05/paper.5.jpg"))

        # Move the JPEG around
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_pdf, 4,
            self.doc_pdf, 3
        )
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/paper.4.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 4
        ).endswith("20200525_1241_05/doc.pdf#page=4"))

        # Move the JPEG around again
        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_pdf, 3,
            self.doc_pdf, 1
        )
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 0
        ).endswith("20200525_1241_05/doc.pdf#page=1"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 1
        ).endswith("20200525_1241_05/paper.2.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 2
        ).endswith("20200525_1241_05/paper.3.edited.jpg"))
        self.assertTrue(self.core.call_success(
            PageImg.page_get_img_url, self.doc_pdf, 3
        ).endswith("20200525_1241_05/doc.pdf#page=3"))
        self.assertTrue(self.core.call_success(  # bug #245: returned None here
            PageImg.page_get_img_url, self.doc_pdf, 4
        ).endswith("20200525_1241_05/doc.pdf#page=4"))


class TestBug1(BaseTest):
    def setUp(self):
        super().setUp()

        self.doc_a = self.core.call_success(
            Fs.fs_join, self.work_dir_url, "20200525_1241_05"
        )
        self._copy_pdf(self.doc_a + "/doc.pdf")
        self._make_file(self.doc_a + "/paper.1.edited.png")
        self._make_file(self.doc_a + "/paper.1.words")
        self._make_file(self.doc_a + "/paper.2.edited.png")
        self._make_file(self.doc_a + "/paper.2.words")
        self._make_file(self.doc_a + "/paper.3.edited.png")
        self._make_file(self.doc_a + "/paper.3.words")

        self.doc_b = self.core.call_success(
            Fs.fs_join, self.work_dir_url, "20200525_1441_05"
        )
        self._make_file(self.doc_b + "/paper.1.png")
        self._make_file(self.doc_b + "/paper.1.edited.png")
        self._make_file(self.doc_b + "/paper.1.words")

    def test_bug_1(self):
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_a)
        self.assertEqual(nb, 4)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 1)

        self.core.call_all(
            PageManagement.page_move_by_url,
            self.doc_a, 1,
            self.doc_b, 1
        )
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_a)
        self.assertEqual(nb, 3)
        nb = self.core.call_success(Docs.doc_get_nb_pages_by_url, self.doc_b)
        self.assertEqual(nb, 2)
