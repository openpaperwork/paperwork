"""
Provides support for URIs "memory://". Those files are actually stored in
memory. It is only useful for temporary files. It has been made as a plugin
so it can easily be disabled on low-memory systems (will fall back on
gio.fs --> real on-disk files).
"""

import io
import itertools
import logging
import time

from . import CommonFsPluginBase


LOGGER = logging.getLogger(__name__)


class _MemoryFileAdapter(io.RawIOBase):
    def __init__(self, plugin, key, mode='r'):
        super().__init__()
        self.plugin = plugin
        self.mode = mode
        self.key = key

        self.io = None
        self.io_cls = io.BytesIO if 'b' in mode else io.StringIO

        if 'r' in mode or 'a' in mode:
            if key not in self.plugin.fs:
                raise FileNotFoundError(key)

            data = self.plugin.fs[key][1]

            if 'b' in mode and isinstance(data, str):
                data = data.encode("utf-8")
            elif 'b' not in mode and isinstance(data, bytes):
                data = data.decode("utf-8")

            self.io = self.io_cls(data)
        elif 'w' in mode:
            self.io = self.io_cls()
            self.plugin.fs[self.key] = (
                time.time(), b"" if 'b' in mode else ""
            )

        self.get_content = (
            self.io.getbuffer if 'b' in mode else self.io.getvalue
        )
        self.read = self.io.read if hasattr(self.io, 'read') else None
        self.readall = self.io.readall if hasattr(self.io, 'readall') else None
        self.readinto = (
            self.io.readinto if hasattr(self.io, 'readinto') else None
        )
        self.readline = (
            self.io.readline if hasattr(self.io, 'readline') else None
        )
        self.readlines = (
            self.io.readlines if hasattr(self.io, 'readlines') else None
        )
        self.seek = self.io.seek if hasattr(self.io, 'seek') else None
        self.tell = self.io.tell if hasattr(self.io, 'tell') else None
        self.truncate = (
            self.io.truncate if hasattr(self.io, 'truncate') else None
        )
        self.write = self.io.write if hasattr(self.io, 'write') else None
        self.writelines = (
            self.io.writelines if hasattr(self.io, 'writelines') else None
        )

    def readable(self):
        return 'r' in self.mode or '+' in self.mode

    def writable(self):
        return 'w' in self.mode or 'a' in self.mode

    def seekable(self):
        return True

    def fileno(self):
        raise io.UnsupportedOperation("fileno() called on memory object")

    def isatty(self):
        return False

    def writelines(self, lines):
        if 'b' in self.mode:
            self.write(b"".join(lines))
        else:
            self.write("".join(lines))

    def flush(self):
        super().flush()
        if hasattr(self.io, 'flush'):
            self.io.flush()
        if 'w' not in self.mode and 'a' not in self.mode:
            return
        if 'b' in self.mode:
            self.plugin.fs[self.key] = (time.time(), bytes(self.get_content()))
        else:
            self.plugin.fs[self.key] = (time.time(), str(self.get_content()))

    def close(self):
        self.flush()
        super().close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class Plugin(CommonFsPluginBase):
    PRIORITY = 100  # to be called first for fs_mktemp

    def __init__(self, core):
        super().__init__(core)
        # self.fs = {id: (mtime, content), id: (mtime, content), ...}
        self.fs = {}
        self.id_gen = itertools.count()

    @staticmethod
    def _get_memory_id(uri):
        if not uri.startswith("memory://"):
            return None
        return uri[len("memory://"):]

    def fs_open(self, uri, mode='r', needs_fileno=False, **kwargs):
        if needs_fileno:
            return None
        mem_id = self._get_memory_id(uri)
        if mem_id is None:
            return None
        return _MemoryFileAdapter(self, mem_id, mode)

    def fs_exists(self, url):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return None
        return mem_id in self.fs

    def fs_listdir(self, url):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return

        mem_id += '/'
        out = []

        for k in self.fs.keys():
            if k.startswith(mem_id) and '/' not in k[len(mem_id):]:
                out.append(k)

        return out

    def fs_rename(self, old_url, new_url):
        old_mem_id = self._get_memory_id(old_url)
        new_mem_id = self._get_memory_id(old_url)

        if old_mem_id is None or new_mem_id is None:
            return

        f = self.fs.pop(old_mem_id)
        self.fs[new_mem_id] = f
        return True

    def fs_unlink(self, url, **kwargs):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return
        self.fs.pop(mem_id)
        return True

    def fs_rm_rf(self, url, **kwargs):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return

        if mem_id in self.fs:
            self.fs.pop(mem_id)

        mem_id += '/'
        for k in list(self.fs.keys()):
            if k.startswith(mem_id):
                self.fs.pop(k)

        return True

    def fs_get_mtime(self, url):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return
        return self.fs[mem_id][0]

    def fs_getsize(self, url):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return
        return len(self.fs[mem_id][1])

    def fs_isdir(self, url):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return None

        mem_id += '/'
        for k in list(self.fs.keys()):
            if k.startswith(mem_id):
                return True
        return None

    def fs_copy(self, old_url, new_url):
        old_mem_id = self._get_memory_id(old_url)
        new_mem_id = self._get_memory_id(old_url)

        if old_mem_id is None and new_mem_id is None:
            return None

        if old_mem_id is None or new_mem_id is None:
            # One memory url, one local filesystem url
            # use the more generic and cross-FS method
            return super().fs_copy(old_url, new_url)

        self.fs[new_mem_id] = self.fs[old_mem_id]
        return new_url

    def fs_mkdir_p(self, url):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return None
        # nothing to do actually
        return True

    def fs_recurse(self, parent_url, dir_included=False):
        mem_id = self._get_memory_id(parent_url)
        if mem_id is None:
            return

        mem_id += '/'
        out = []

        for k in self.fs.keys():
            if k.startswith(mem_id):
                out.append(k)

        return out

    def fs_hide(self, url):
        return None

    def fs_get_mime(self, url):
        return None

    def fs_iswritable(self, url):
        mem_id = self._get_memory_id(url)
        if mem_id is None:
            return None
        return True

    def fs_mktemp(
                self, prefix=None, suffix=None, mode='w+b', on_disk=False,
                **kwargs
            ):
        assert prefix is None or '/' not in prefix
        assert suffix is None or '/' not in suffix
        if on_disk:
            return
        name = "{}{}{}".format(
            prefix if prefix is not None else "",
            next(self.id_gen),
            suffix if suffix is not None else ""
        )
        return ("memory://" + name, _MemoryFileAdapter(self, name, mode))

    def fs_resolve(self, uri):
        if not uri.startswith("memory://"):
            return None
        return uri
