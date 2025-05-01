import logging
import unittest

import openpaperwork_core

from paperwork_backend.interfaces.chkworkdir import Chkworkdir


LOGGER = logging.getLogger(__name__)


class TestChkWorkDirEmptyDirectory(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.chkworkdir.empty_doc")
        self.core.init()

        self.config = self.core.get_by_name("openpaperwork_core.config.fake")
        self.config.settings = {
            "workdir": "file:///some_work_dir"
        }
        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_no_problem(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc_a": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "some_doc_b": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
            },
        }

        problems = []
        self.core.call_all(Chkworkdir.check_work_dir, problems)
        self.assertEqual(len(problems), 0)

    def test_check_fix(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc_a": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "some_doc_b": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "some_doc_empty": {},
            },
        }

        problems = []
        self.core.call_all(Chkworkdir.check_work_dir, problems)
        self.assertEqual(len(problems), 1)

        self.core.call_all(Chkworkdir.fix_work_dir, problems)
        self.assertEqual(
            self.fs.fs,
            {
                "some_work_dir": {
                    "some_doc_a": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                    },
                    "some_doc_b": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                    },
                },
            }
        )
