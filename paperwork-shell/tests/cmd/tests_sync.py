import argparse
import datetime
import os
import shutil
import tempfile
import unittest

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.quit import QuitListener
from openpaperwork_core.interfaces.shell import Shell
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
        self.core.call_all(QuitListener.on_quit)
        shutil.rmtree(self.tmp_local_dir)
        shutil.rmtree(self.tmp_work_dir)

    def test_sync(self):
        config = self.core.get_by_name("openpaperwork_core.config.fake")
        config.settings = {
            "workdir": openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
                self.tmp_work_dir
            ),
        }

        self.core.load("paperwork_backend.guesswork.label.sklearn")
        self.core.load("paperwork_backend.guesswork.ocr.pyocr")
        self.core.load("paperwork_backend.index.whoosh")
        self.core.load("paperwork_backend.model.hocr")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.labels")
        self.core.load("paperwork_backend.model.pdf")
        self.core.load("paperwork_shell.cmd.sync")
        self.core.init()

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all(Shell.cmd_complete_argparse, cmd_parser)

        args = parser.parse_args(['sync'])
        self.core.call_all(
            Shell.cmd_set_console, openpaperwork_core.cmd.DummyConsole()
        )

        # start with an empty work directory

        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(r, {})

        # add 2 documents, one PDF and one img+hocr

        doc_a = os.path.join(self.tmp_work_dir, "20190801_1733_23")
        os.mkdir(doc_a)
        shutil.copyfile(self.test_pdf, os.path.join(doc_a, "doc.pdf"))

        doc_b = os.path.join(self.tmp_work_dir, "20190830_1916_32")
        os.mkdir(doc_b)
        shutil.copyfile(self.test_img, os.path.join(doc_b, "paper.1.jpg"))
        shutil.copyfile(self.test_hocr, os.path.join(doc_b, "paper.1.words"))

        r = self.core.call_success(Shell.cmd_run, self.console, args)
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

            class Plugin(
                openpaperwork_core.PluginBase,
                Fs,
            ):
                PRIORITY = 9999999999

                def fs_get_mtime(s, file_url):
                    if file_url.endswith(".words"):
                        dt = datetime.datetime(year=2038, month=1, day=1)
                        return dt.timestamp()
                    return None

                def fs_safe(self, uri):
                    pass

                def fs_unsafe(self, uri):
                    pass

                def fs_join(self, base, url):
                    pass

                def fs_basename(self, url):
                    pass

                def fs_dirname(self, url):
                    pass

                def fs_hash(self, url):
                    pass

                def fs_open(self, uri, mode='r', **kwargs):
                    pass

                def fs_exists(self, uri):
                    pass

                def fs_listdir(self, uri):
                    pass

                def fs_rename(self, old_uri, new_uri):
                    pass

                def fs_unlink(self, uri, **kwargs):
                    pass

                def fs_rm_rf(self, uri, **kwargs):
                    pass

                def fs_getsize(self, uri):
                    pass

                def fs_isdir(self, uri):
                    pass

                def fs_copy(self, old_uri, new_uri):
                    pass

                def fs_copytree(self, old_uri, new_uri):
                    pass

                def fs_mkdir_p(self, uri):
                    pass

                def fs_recurse(self, parent_uri, dir_included=False):
                    pass

                def fs_hide(self, uri):
                    pass

                def fs_get_mime(self, uri):
                    pass

                def fs_iswritable(self, uri):
                    pass

                def fs_resolve(self, uri):
                    pass

                def fs_mktemp(
                    self, prefix=None, suffix=None, mode='w+b', on_disk=False,
                    **kwargs
                ):
                    pass

        self.core.load("fake_module", FakeModule())
        self.core.init()

        r = self.core.call_success(Shell.cmd_run, self.console, args)
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

        r = self.core.call_success(Shell.cmd_run, self.console, args)
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
