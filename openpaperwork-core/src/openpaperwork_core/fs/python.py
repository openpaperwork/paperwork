"""
Provides support for URIs "file://".
"""

import codecs
import logging
import os
import os.path
import shutil
import tempfile

from . import CommonFsPluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(CommonFsPluginBase):
    def __init__(self):
        super().__init__()
        self.tmp_files = set()

    def _uri_to_path(self, uri):
        if not uri.lower().startswith("file://"):
            return None
        return self.fs_unsafe(uri)

    def fs_open(self, uri, mode='r', **kwargs):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        if 'w' not in mode and 'a' not in mode and not os.path.exists(path):
            return None

        if 'b' in mode:
            return open(path, mode)
        return codecs.open(path, mode, encoding='utf-8')

    def fs_exists(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        r = os.path.exists(path)
        if not r:
            return None
        return r

    def fs_listdir(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return None
        if not os.path.exists(path):
            return None
        for f in os.listdir(path):
            yield self.fs_safe(os.path.join(path, f))

    def fs_rename(self, old_uri, new_uri):
        old_path = self._uri_to_path(old_uri)
        new_path = self._uri_to_path(new_uri)
        if old_path is None or new_path is None:
            return None
        if not os.path.exists(old_path):
            return None

        os.rename(old_path, new_path)
        return True

    def fs_unlink(self, uri, **kwargs):
        path = self._uri_to_path(uri)
        if path is None:
            return

        if not os.path.exists(path):
            return None
        os.unlink(path)
        return True

    def fs_rm_rf(self, uri, **kwargs):
        path = self._uri_to_path(uri)
        if path is None:
            return

        shutil.rmtree(path, ignore_errors=True)
        return True

    def fs_get_mtime(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        return int(os.stat(path).st_mtime)

    def fs_getsize(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        return os.stat(path).st_size

    def fs_isdir(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        if os.path.isdir(path):
            return True
        return None

    def fs_copy(self, old_uri, new_uri):
        old_path = self._uri_to_path(old_uri)
        new_path = self._uri_to_path(new_uri)
        if old_path is None or new_path is None:
            return None

        shutil.copy(old_path, new_path)
        return True

    def fs_copytree(self, old_uri, new_uri):
        old_path = self._uri_to_path(old_uri)
        new_path = self._uri_to_path(new_uri)
        if old_path is None or new_path is None:
            return None

        shutil.copytree(old_path, new_path)
        return True

    def fs_mkdir_p(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        os.makedirs(path, mode=0o700, exist_ok=True)
        return True

    def fs_recurse(self, parent_uri, dir_included=False):
        path = self._uri_to_path(parent_uri)
        if path is None:
            return

        for (root, dirs, files) in os.walk(path):
            if dir_included:
                for d in dirs:
                    p = os.path.join(path, root, d)
                    yield self.fs_safe(p)
            for f in files:
                p = os.path.join(path, root, f)
                yield self.fs_safe(p)

    def fs_hide(self, uri):
        pass

    def fs_get_mime(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        # should use 'magic', but Core can't have any dependency on it.
        # other we would pull it on all platforms.
        path = path.lower()
        if path.endswith(".pdf"):
            return "application/pdf"
        if path.endswith(".png"):
            return "image/png"
        if path.endswith(".tiff"):
            return "image/tiff"
        if path.endswith(".bmp"):
            return "image/x-ms-bmp"
        if path.endswith(".jpeg") or path.endswith(".jpg"):
            return "image/jpeg"
        if path.endswith(".txt"):
            return "text/plain"

        return None

    def fs_iswritable(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        return os.access(path, os.W_OK)

    def fs_mktemp(
                self, prefix=None, suffix=None, mode='w+b', on_disk=False,
                **kwargs
            ):
        if 'b' not in mode:
            tmp = tempfile.NamedTemporaryFile(
                prefix=prefix, suffix=suffix, delete=False, mode=mode,
                encoding='utf-8'
            )
        else:
            tmp = tempfile.NamedTemporaryFile(
                prefix=prefix, suffix=suffix, delete=False, mode=mode
            )
        self.tmp_files.add(tmp.name)
        return (self.fs_safe(tmp.name), tmp)

    def on_quit(self):
        for tmp_file in self.tmp_files:
            try:
                os.unlink(tmp_file)
            except FileNotFoundError:
                pass
