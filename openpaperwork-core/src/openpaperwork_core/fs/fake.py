"""
Mock implementation of the plugin interface 'fs'.
Useful for tests only.
"""

import io
import logging
import os

from . import CommonFsPluginBase
from . import memory

LOGGER = logging.getLogger(__name__)


class FakeFileAdapter(io.RawIOBase):
    def __init__(self, fs_plugin, path, content, mode='r'):
        super().__init__()
        self.fs_plugin = fs_plugin
        self.path = path
        self.content = content if 'w' not in mode else None
        self.pos = len(self.content) if 'a' in mode else 0
        self.mode = mode

        if self.content is None:
            self.content = b'' if 'b' in mode else ''

    def readable(self):
        return True

    def writable(self):
        return 'w' in self.mode or 'a' in self.mode

    def read(self, size=-1):
        if size < 0:
            r = len(self.content[self.pos:])
        else:
            r = min(size, len(self.content[self.pos:]))
        out = self.content[self.pos:self.pos + r]
        self.pos += r
        return out

    def readall(self):
        return self.content

    def readinto(self, b):
        raise NotImplementedError()

    def readline(self, size=-1):
        r = self.content[self.pos:]
        r = r.split("\n", 1)
        self.pos += len(r[0]) + 1
        return r[0] + "\n"

    def readlines(self, hint=-1):
        self.pos = len(self.content)
        return [
            r + "\n"
            for r in self.content.split("\n")
        ]

    def seek(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_CUR:
            self.pos += offset
        elif whence == os.SEEK_SET:
            self.pos = offset
        else:
            raise NotImplementedError()

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def flush(self):
        pass

    def truncate(self, size=None):
        raise NotImplementedError()

    def isatty(self):
        return False

    def write(self, b):
        self.content = self.content[:self.pos]
        self.content += b
        self.pos += len(b)
        return len(b)

    def writelines(self, lines):
        raise NotImplementedError()

    def close(self):
        if 'a' in self.mode or 'w' in self.mode:
            d = self.fs_plugin.fs
            for p in self.path[:-1]:
                d = d[p]
            d[self.path[-1]] = self.content
        self.flush()
        super().close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class Plugin(CommonFsPluginBase):
    def __init__(self, fs=None):
        """
        Test implementation.

        `fs` should have the following format:

        {
            'base_dir': {
                'sub_dir_a': {},
                'sub_dir_b': {
                    'file_a': "content_file_a",
                    'file_b': "content_file_b",
                }
            }
        }
        """
        super().__init__()
        if fs is None:
            self.fs = {}
        else:
            self.fs = fs

    @staticmethod
    def _get_path(url):
        assert url.lower().startswith("file:///")
        url = url[len('file:///'):]
        return url.split('/')

    def fs_open(self, url, mode='r', **kwargs):
        path = self._get_path(url)

        f = self.fs
        for p in path[:-1]:
            f = f[p]
        if path[-1] in f:
            f = f[path[-1]]
            assert isinstance(f, str) or isinstance(f, bytes)
        elif 'b' in mode:
            f = b""
        else:
            f = ""
        return FakeFileAdapter(self, path, f, mode)

    def fs_exists(self, url):
        path = self._get_path(url)
        f = self.fs
        for p in path:
            if p not in f:
                return None
            f = f[p]
        return True

    def fs_listdir(self, url):
        path = self._get_path(url)
        f = self.fs
        for p in path:
            try:
                f = f[p]
            except KeyError:
                return None
        assert isinstance(f, dict)
        return [url + "/" + k for k in f.keys()]

    def fs_rename(self, old_url, new_url):
        old_path = self._get_path(old_url)
        old_dir = self.fs
        for p in old_path[:-1]:
            old_dir = old_dir[p]

        new_path = self._get_path(new_url)
        new_dir = self.fs
        for p in new_path[:-1]:
            new_dir = new_dir[p]

        old_file = old_dir.pop(old_path[-1])
        new_dir[new_path[-1]] = old_file

    def fs_unlink(self, url, **kwargs):
        self.fs_rm_rf(url)

    def fs_rm_rf(self, url, **kwargs):
        path = self._get_path(url)
        f = self.fs
        for p in path[:-1]:
            if p not in f:
                return None
            f = f[p]
        assert isinstance(f, dict)
        filename = url.split("/")[-1]
        if filename in f:
            f.pop(filename)
            return True
        return None

    def fs_get_mtime(self, url):
        return 0

    def fs_getsize(self, url):
        path = self._get_path(url)
        f = self.fs
        for p in path:
            f = f[p]
        return len(f)

    def fs_isdir(self, url):
        path = self._get_path(url)
        f = self.fs
        for p in path:
            if p not in f:
                return None
            f = f[p]
        if isinstance(f, dict):
            return True
        return None

    def fs_copy(self, old_url, new_url):
        raise NotImplementedError()

    def fs_copytree(self, old_url, new_url):
        raise NotImplementedError()

    def fs_mkdir_p(self, url):
        path = self._get_path(url)
        f = self.fs
        for p in path[:-1]:
            if p not in f:
                f[p] = {}
            f = f[p]
        name = url.split("/")[-1]
        if name not in f:
            f[name] = {}
        return True

    def fs_recurse(self, parent_uri, dir_included=False):
        raise NotImplementedError()

    def fs_hide(self, uri):
        pass

    def fs_get_mime(self, uri):
        pass

    def fs_iswritable(self, url):
        return True

    def fs_mktemp(self, prefix=None, suffix=None, mode='w+b', **kwargs):
        name = "file://tmp/temporary_file" + suffix
        return (name, memory.MemoryFileAdapter(self, name, mode))
