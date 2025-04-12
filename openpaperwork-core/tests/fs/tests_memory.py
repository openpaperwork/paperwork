import unittest

from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core


class TestSafe(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.fs.memory")
        self.core.init()

    def test_write_read_bytes(self):
        with self.core.call_success(
                    Fs.fs_open, "memory://test_file", mode="wb"
                ) as file_desc:
            file_desc.write(b"abcdef")
            file_desc.write(b"ghijf")

        with self.core.call_success(
                    Fs.fs_open, "memory://test_file", mode="rb"
                ) as file_desc:
            r = file_desc.read()
            self.assertEqual(r, b'abcdefghijf')

        self.core.call_success(Fs.fs_unlink, "memory://test_file", trash=False)

    def test_write_read_string(self):
        with self.core.call_success(
                    Fs.fs_open, "memory://test_file", mode="w"
                ) as file_desc:
            file_desc.write("abcdef\n")
            file_desc.write("ghijf\n")

        with self.core.call_success(
                    Fs.fs_open, "memory://test_file", mode="r"
                ) as file_desc:
            r = file_desc.readlines()
            self.assertEqual(r, [
                'abcdef\n',
                'ghijf\n'
            ])

        self.core.call_success(Fs.fs_unlink, "memory://test_file", trash=False)

    def test_write_read_tempfile(self):
        (name, file_desc) = self.core.call_success(
            Fs.fs_mktemp, "camion", "tulipe", mode="w"
        )
        with file_desc:
            self.assertTrue(name.startswith("memory://"))
            file_desc.write("abcdef\n")
            file_desc.write("ghijf\n")

        with self.core.call_success(Fs.fs_open, name, mode="r") as file_desc:
            r = file_desc.readlines()
            self.assertEqual(r, [
                'abcdef\n',
                'ghijf\n'
            ])

        self.core.call_success(Fs.fs_unlink, name, trash=False)
