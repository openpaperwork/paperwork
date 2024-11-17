import os
import pathlib
import tempfile
import time
import unittest

import openpaperwork_core


class AbstractTestSafe(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_relative(self):
        # make sure it's turned into an absolute path
        v = self.core.call_one('fs_safe', 'jerome')
        self.assertTrue(v.startswith("file:///"))

    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_linux(self):
        v = self.core.call_one('fs_safe', '/home/flesch jerome')
        self.assertEqual(v, "file:///home/flesch%20jerome")

        v = self.core.call_one('fs_safe', 'file:///home/flesch%20jerome')
        self.assertEqual(v, "file:///home/flesch%20jerome")

    @unittest.skipUnless(os.name == 'nt', reason="Windows only")
    def test_windows(self):
        v = self.core.call_one('fs_safe', 'c:\\Users\\flesch jerome')
        self.assertEqual(v, "file:///c:/Users/flesch%20jerome")

        v = self.core.call_one('fs_safe', '\\\\someserver\\someshare')
        self.assertEqual(v, "\\\\someserver\\someshare")


class AbstractTestUnsafe(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_linux(self):
        v = self.core.call_one('fs_unsafe', 'file:///home/flesch%20jerome')
        self.assertEqual(v, "/home/flesch jerome")

        v = self.core.call_one('fs_unsafe', 'file:///home/flesch jerome')
        self.assertEqual(v, "/home/flesch jerome")

        v = self.core.call_one('fs_unsafe', '/home/flesch jerome')
        self.assertEqual(v, "/home/flesch jerome")

    @unittest.skipUnless(os.name == 'nt', reason="Windows only")
    def test_windows(self):
        v = self.core.call_success(
            'fs_unsafe', 'file://c:\\Users\\flesch%20jerome'
        )
        self.assertEqual(v, "c:\\Users\\flesch jerome")

        v = self.core.call_one('fs_safe', '\\\\someserver\\someshare')
        self.assertEqual(v, "\\\\someserver\\someshare")


class AbstractTestOpen(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_read_binary(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as fd:
            file_name = fd.name
            fd.write(b"content")
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            with self.core.call_one(
                        'fs_open', safe_file_name, mode='rb'
                    ) as fd:
                content = fd.read()
                self.assertEqual(content, b"content")
        finally:
            os.unlink(file_name)

    def test_write_binary(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as fd:
            file_name = fd.name
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            with self.core.call_one(
                        'fs_open', safe_file_name, mode='wb'
                    ) as fd:
                fd.write(b"content\n")
            with open(file_name, 'rb') as fd:
                content = fd.read()
                self.assertEqual(content, b"content\n")
        finally:
            os.unlink(file_name)

    def test_read(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            with self.core.call_one('fs_open', safe_file_name, mode='r') as fd:
                content = fd.read()
                self.assertEqual(content, "content")
        finally:
            os.unlink(file_name)

    def test_write(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            with self.core.call_one('fs_open', safe_file_name, mode='w') as fd:
                fd.write("content\n")
            with open(file_name, 'r') as fd:
                content = fd.read()
                self.assertEqual(content, "content\n")
        finally:
            os.unlink(file_name)


class AbstractTestExists(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_not_exist(self):
        self.assertEqual(self.core.call_one('fs_exists', "/whatever"), None)

    def test_exists(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            self.assertTrue(self.core.call_one('fs_exists', safe_file_name))
        finally:
            os.unlink(file_name)


class AbstractTestListDir(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

        self.dirname = tempfile.mkdtemp()
        self.uri_dirname = self.core.call_one('fs_safe', self.dirname)
        with open(os.path.join(self.dirname, 'test1.txt'), 'w') as fd:
            fd.write('test1')
        with open(os.path.join(self.dirname, 'test2.txt'), 'w') as fd:
            fd.write('test2')
        os.mkdir(os.path.join(self.dirname, 'test3'))
        with open(os.path.join(self.dirname, 'test3', 'test4.txt'), 'w') as fd:
            fd.write('test4')

    def tearDown(self):
        # check fs_rm_rf at the same time
        self.core.call_one("fs_rm_rf", self.uri_dirname, trash=False)
        self.assertFalse(os.path.exists(self.dirname))

    def test_listdir(self):
        files = list(self.core.call_one('fs_listdir', self.uri_dirname))
        files.sort()

        self.assertEqual(files, [
            self.uri_dirname + '/test1.txt',
            self.uri_dirname + '/test2.txt',
            self.uri_dirname + '/test3'
        ])

    def test_recurse(self):
        files = list(self.core.call_one('fs_recurse', self.uri_dirname))
        files.sort()

        self.assertEqual(files, [
            self.uri_dirname + '/test1.txt',
            self.uri_dirname + '/test2.txt',
            self.uri_dirname + '/test3/test4.txt'
        ])


class AbstractTestRename(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_rename(self):
        src_file_name = None
        dst_file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            src_file_name = fd.name
            fd.write("content")
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            dst_file_name = fd.name
            fd.write("content")
        os.unlink(dst_file_name)

        try:
            safe_src_file_name = self.core.call_one('fs_safe', src_file_name)
            safe_dst_file_name = self.core.call_one('fs_safe', dst_file_name)
            self.assertTrue(os.path.exists(src_file_name))
            self.assertFalse(os.path.exists(dst_file_name))

            self.core.call_one(
                'fs_rename', safe_src_file_name, safe_dst_file_name
            )
            self.assertFalse(os.path.exists(src_file_name))
            self.assertTrue(os.path.exists(dst_file_name))
        finally:
            if os.path.exists(src_file_name):
                os.unlink(src_file_name)
            if os.path.exists(dst_file_name):
                os.unlink(dst_file_name)


class AbstractTestUnlink(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_unlink(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")

        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            self.assertTrue(os.path.exists(file_name))

            self.core.call_one('fs_unlink', safe_file_name, trash=False)
            self.assertFalse(os.path.exists(file_name))
        finally:
            if os.path.exists(file_name):
                os.unlink(file_name)


class AbstractTestGetMtime(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_get_mtime(self):
        now = time.time()

        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")

        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            mtime = self.core.call_one('fs_get_mtime', safe_file_name)
            self.assertTrue(int(now) <= mtime)
            self.assertTrue(mtime <= now + 2)

            time.sleep(2)  # :-(

            with open(file_name, 'a') as fd:
                fd.write("content")
            new_mtime = self.core.call_one('fs_get_mtime', safe_file_name)
            self.assertTrue(int(now) <= new_mtime)
            self.assertTrue(mtime < new_mtime)
        finally:
            os.unlink(file_name)


class AbstractTestGetsize(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_getsize(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")  # 7 bytes

        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)

            s = self.core.call_one('fs_getsize', safe_file_name)
            self.assertEqual(s, 7)
        finally:
            os.unlink(file_name)


class AbstractTestIsdir(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_isdir_true(self):
        dirname = tempfile.mkdtemp()
        uri_dirname = self.core.call_one('fs_safe', dirname)

        try:
            self.assertTrue(self.core.call_one("fs_isdir", uri_dirname))
        finally:
            # check fs_rm_rf at the same time
            self.core.call_one("fs_rm_rf", uri_dirname, trash=False)
            self.assertFalse(os.path.exists(dirname))

    def test_isdir_false(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")

        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)

            self.assertFalse(self.core.call_one('fs_isdir', safe_file_name))
        finally:
            os.unlink(file_name)


class AbstractTestCopy(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_copy(self):
        src_file_name = None
        dst_file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            src_file_name = fd.name
            fd.write("content")
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            dst_file_name = fd.name
            fd.write("xxxxxxx")
        os.unlink(dst_file_name)

        try:
            safe_src_file_name = self.core.call_one('fs_safe', src_file_name)
            safe_dst_file_name = self.core.call_one('fs_safe', dst_file_name)
            self.assertTrue(os.path.exists(src_file_name))
            self.assertFalse(os.path.exists(dst_file_name))

            self.core.call_one(
                'fs_copy', safe_src_file_name, safe_dst_file_name
            )
            self.assertTrue(os.path.exists(src_file_name))
            self.assertTrue(os.path.exists(dst_file_name))

            with open(dst_file_name, 'r') as fd:
                content = fd.read()
                self.assertEqual(content, 'content')
        finally:
            if os.path.exists(src_file_name):
                os.unlink(src_file_name)
            if os.path.exists(dst_file_name):
                os.unlink(dst_file_name)

    def test_copytree(self):
        with tempfile.TemporaryDirectory() as root:
            root = pathlib.Path(root)
            (root / "src").mkdir()
            (root / "src" / "sub").mkdir()
            with (root / "src" / "test.txt").open("w") as fd:
                fd.write("CONTENT1\n")
            with (root / "src" / "sub" / "test.txt").open("w") as fd:
                fd.write("CONTENT2\n")

            self.core.call_success(
                "fs_copytree",
                self.core.call_success("fs_safe", (root / "src")),
                self.core.call_success("fs_safe", (root / "dst")),
            )

            with (root / "dst" / "test.txt").open() as fd:
                self.assertEqual(fd.read(), "CONTENT1\n")
            with (root / "dst" / "sub" / "test.txt").open() as fd:
                self.assertEqual(fd.read(), "CONTENT2\n")


class AbstractTestMkdirP(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_mkdir_p(self):
        dirname = tempfile.mkdtemp()
        uri_dirname = self.core.call_one('fs_safe', dirname)
        try:
            new_dirs = uri_dirname + "/testA/testB/testC"
            self.core.call_one("fs_mkdir_p", new_dirs)
            self.assertTrue(os.path.exists(os.path.join(
                dirname, "testA", "testB", "testC"
            )))
        finally:
            # check fs_rm_rf at the same time
            self.core.call_one("fs_rm_rf", uri_dirname, trash=False)
            self.assertFalse(os.path.exists(dirname))


class AbstractTestBasename(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_basename(self):
        out = self.core.call_success("fs_basename", "file:///a/b/c.txt")
        self.assertEqual(out, "c.txt")
        out = self.core.call_success("fs_basename", "file:///c.txt")
        self.assertEqual(out, "c.txt")
        out = self.core.call_success("fs_basename", "memory://camion.txt")
        self.assertEqual(out, "camion.txt")


class AbstractTestTemp(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_mktemp(self):
        (tmp_url, tmp_fd) = self.core.call_success(
            "fs_mktemp", prefix="test", suffix=".txt", mode="w"
        )
        with tmp_fd:
            tmp_fd.write("TEST\n")

        self.assertNotEqual(
            self.core.call_success("fs_exists", tmp_url), None
        )

        self.core.call_all("on_quit")

        self.assertEqual(
            self.core.call_success("fs_exists", tmp_url), None
        )


class AbstractTestResolve(unittest.TestCase):
    def get_plugin_name(self) -> str:
        """
        must be subclassed
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_resolve(self):
        uri = self.core.call_success("fs_resolve", "file:///var/www/../../etc/passwd")
        self.assertEqual(uri, "file:///etc/passwd")
