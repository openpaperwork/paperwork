import argparse
import datetime
import os
import shutil
import tempfile
import unittest

import openpaperwork_core
import openpaperwork_core.cmd
import openpaperwork_core.fs


class TestSync(unittest.TestCase):
    def setUp(self):
        self.console = openpaperwork_core.cmd.DummyConsole()

        self.test_img = "{}/test_img.jpeg".format(
            os.path.dirname(os.path.abspath(__file__))
        )
        self.test_hocr = "{}/test_txt.hocr".format(
            os.path.dirname(os.path.abspath(__file__))
        )
        self.test_pdf = "{}/test_doc.pdf".format(
            os.path.dirname(os.path.abspath(__file__))
        )

        self.tmp_local_dir = tempfile.mkdtemp()
        self.tmp_work_dir = tempfile.mkdtemp()
        os.environ['XDG_DATA_HOME'] = self.tmp_local_dir

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.init()

    def tearDown(self):
        self.core.call_all("tests_cleanup")
        shutil.rmtree(self.tmp_local_dir)
        shutil.rmtree(self.tmp_work_dir)

    def test_sync(self):
        config = self.core.get_by_name("openpaperwork_core.config.fake")
        config.settings = {
            "workdir": openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
                self.tmp_work_dir
            ),
        }

        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.hocr")
        self.core.load("paperwork_backend.model.pdf")
        self.core.load("paperwork_shell.cmd.sync")

        self.core.init()

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all("cmd_complete_argparse", cmd_parser)

        args = parser.parse_args(['sync'])
        self.core.call_all(
            "cmd_set_console", openpaperwork_core.cmd.DummyConsole()
        )

        # start with an empty work directory

        r = self.core.call_success("cmd_run", self.console, args)
        self.assertEqual(r, {})

        # add 2 documents, one PDF and one img+hocr

        doc_a = os.path.join(self.tmp_work_dir, "20190801_1733_23")
        os.mkdir(doc_a)
        shutil.copyfile(self.test_pdf, os.path.join(doc_a, "doc.pdf"))

        doc_b = os.path.join(self.tmp_work_dir, "20190830_1916_32")
        os.mkdir(doc_b)
        shutil.copyfile(self.test_img, os.path.join(doc_b, "paper.1.jpg"))
        shutil.copyfile(self.test_hocr, os.path.join(doc_b, "paper.1.words"))

        r = self.core.call_success("cmd_run", self.console, args)
        self.assertEqual(r, {
            'whoosh': {
                'added': ['20190801_1733_23', '20190830_1916_32'],
            },
            'ocr': {
                'added': ['20190801_1733_23', '20190830_1916_32'],
            },
            'label_guesser': {
                'added': ['20190801_1733_23', '20190830_1916_32'],
            },
            'doc_tracker': {
                'added': ['20190801_1733_23', '20190830_1916_32'],
            },
        })

        # modify one document

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 9999999999

                def fs_get_mtime(s, file_url):
                    if file_url.endswith(".words"):
                        dt = datetime.datetime(year=2038, month=1, day=1)
                        return dt.timestamp()
                    return None

        self.core._load_module("fake_module", FakeModule())
        self.core.init()

        r = self.core.call_success("cmd_run", self.console, args)
        self.assertEqual(r, {
            'whoosh': {
                'updated': ['20190830_1916_32'],
            },
            'ocr': {
                'updated': ['20190830_1916_32'],
            },
            'label_guesser': {
                'updated': ['20190830_1916_32'],
            },
            'doc_tracker': {
                'updated': ['20190830_1916_32'],
            },
        })

        # delete one document

        shutil.rmtree(doc_a)

        r = self.core.call_success("cmd_run", self.console, args)
        self.assertEqual(r, {
            'whoosh': {
                'deleted': ['20190801_1733_23'],
            },
            'ocr': {
                'deleted': ['20190801_1733_23'],
            },
            'label_guesser': {
                'deleted': ['20190801_1733_23'],
            },
            'doc_tracker': {
                'deleted': ['20190801_1733_23'],
            },
        })
