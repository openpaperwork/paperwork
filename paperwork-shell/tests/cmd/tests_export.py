import argparse
import os
import shutil
import tempfile
import unittest

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
        self.tmp_out_dir = tempfile.mkdtemp()
        os.environ['XDG_DATA_HOME'] = self.tmp_local_dir

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.init()

        self.work_dir_url = openpaperwork_core.fs.CommonFsPluginBase.fs_safe(
            self.tmp_work_dir
        )
        config = self.core.get_by_name("openpaperwork_core.config.fake")
        config.settings = {
            "workdir": self.work_dir_url,
        }

        self.core.load("paperwork_shell.cmd.export")
        self.core.init()

        doc = os.path.join(self.tmp_work_dir, "20190801_1733_23")
        os.mkdir(doc)
        shutil.copyfile(self.test_pdf, os.path.join(doc, "doc.pdf"))

        doc = os.path.join(self.tmp_work_dir, "20190830_1916_32")
        os.mkdir(doc)
        shutil.copyfile(self.test_img, os.path.join(doc, "paper.1.jpg"))
        shutil.copyfile(self.test_hocr, os.path.join(doc, "paper.1.words"))

    def tearDown(self):
        self.core.call_all(QuitListener.on_quit)
        shutil.rmtree(self.tmp_local_dir)
        shutil.rmtree(self.tmp_work_dir)
        shutil.rmtree(self.tmp_out_dir)

    def test_export_doc(self):
        self.core.call_all(
            Shell.cmd_set_console, openpaperwork_core.cmd.DummyConsole()
        )

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all(Shell.cmd_complete_argparse, cmd_parser)

        args = parser.parse_args([
            'export', '20190830_1916_32'  # img doc
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'doc_to_pages',
        ])

        args = parser.parse_args([
            'export', '20190801_1733_23'  # pdf doc
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'doc_to_pages',
            'unmodified_pdf',
        ])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-f', 'doc_to_pages',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'img_boxes',
        ])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-f', 'doc_to_pages',
            '-f', 'img_boxes',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'bmp',
            'bw',
            'generated_pdf',
            'gif',
            'grayscale',
            'jpeg',
            'png',
            'swt_hard',
            'swt_soft',
            'tiff',
            'unpaper',
        ])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-f', 'doc_to_pages',
            '-f', 'img_boxes',
            '-f', 'grayscale',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'bmp',
            'bw',
            'generated_pdf',
            'gif',
            'grayscale',  'jpeg',
            'png',
            'swt_hard',
            'swt_soft',
            'tiff',
            'unpaper',
        ])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-f', 'doc_to_pages',
            '-f', 'img_boxes',
            '-f', 'grayscale',
            '-f', 'generated_pdf',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-f', 'doc_to_pages',
            '-f', 'img_boxes',
            '-f', 'grayscale',
            '-f', 'generated_pdf',
            '-o', os.path.join(self.tmp_out_dir, 'out.pdf')
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertTrue(r)
        self.assertTrue(
            os.path.exists(
                os.path.join(
                    self.tmp_out_dir, 'out.pdf'
                )
            )
        )

    def test_export_page(self):
        self.core.call_all(
            Shell.cmd_set_console, openpaperwork_core.cmd.DummyConsole()
        )

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all(Shell.cmd_complete_argparse, cmd_parser)

        args = parser.parse_args([
            'export', '20190830_1916_32',  # img doc
            '-p', '1',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'img_boxes',
        ])

        args = parser.parse_args([
            'export', '20190801_1733_23',  # pdf doc
            '-p', '1',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'img_boxes',
        ])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-p', '1',
            '-f', 'doc_to_pages',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertFalse(r)

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-p', '1',
            '-f', 'img_boxes',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'bmp',
            'bw',
            'generated_pdf',
            'gif',
            'grayscale',
            'jpeg',
            'png',
            'swt_hard',
            'swt_soft',
            'tiff',
            'unpaper',
        ])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-p', '1',
            '-f', 'img_boxes',
            '-f', 'grayscale',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [
            'bmp',
            'bw',
            'generated_pdf',
            'gif',
            'grayscale',  'jpeg',
            'png',
            'swt_hard',
            'swt_soft',
            'tiff',
            'unpaper',
        ])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-p', '1',
            '-f', 'img_boxes',
            '-f', 'grayscale',
            '-f', 'generated_pdf',
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertEqual(sorted(r), [])

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-p', '1',
            '-f', 'img_boxes',
            '-f', 'grayscale',
            '-f', 'generated_pdf',
            '-o', os.path.join(self.tmp_out_dir, 'out.pdf')
        ])
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertTrue(r)
        self.assertTrue(
            os.path.exists(
                os.path.join(
                    self.tmp_out_dir, 'out.pdf'
                )
            )
        )

    def test_export_invalid_pipeline(self):
        self.core.call_all(
            Shell.cmd_set_console, openpaperwork_core.cmd.DummyConsole()
        )

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all(Shell.cmd_complete_argparse, cmd_parser)

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-f', 'img_boxes',
            '-f', 'grayscale',
            '-f', 'generated_pdf',
            '-o', os.path.join(self.tmp_out_dir, 'out.pdf')
        ])
        # must not crash
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertFalse(r)
        self.assertFalse(
            os.path.exists(
                os.path.join(
                    self.tmp_out_dir, 'out.pdf'
                )
            )
        )

        args = parser.parse_args([
            'export', '20190830_1916_32',
            '-f', 'img_boxes',
            '-f', 'unmodified_pdf',
            '-o', os.path.join(self.tmp_out_dir, 'out.pdf')
        ])
        # must not crash
        r = self.core.call_success(Shell.cmd_run, self.console, args)
        self.assertFalse(r)
        self.assertFalse(
            os.path.exists(
                os.path.join(
                    self.tmp_out_dir, 'out.pdf'
                )
            )
        )
