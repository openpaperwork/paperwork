#!/usr/bin/env python3

import io
import os
import urllib

from gi.repository import Gio
from gi.repository import GLib


class GioFileAdapter(io.RawIOBase):
    def __init__(self, gfile, mode='r'):
        super().__init__()
        if mode == 'w':
            mode = 'rw'

        self.gfile = gfile
        self.mode = mode

        fi = gfile.query_info(
            Gio.FILE_ATTRIBUTE_STANDARD_SIZE, Gio.FileQueryInfoFlags.NONE
        )
        self.size = fi.get_size()

        self.gfd = None
        self.gin = None
        self.gout = None

        if mode == 'r':
            self.gin = self.gfd = gfile.read()
        elif mode == 'rw':
            if gfile.query_exists():
                self.gfd = gfile.open_readwrite()
            else:
                self.gfd = gfile.create_readwrite()
            self.gin = self.gfd.get_input_stream()
            self.gout = self.gfd.get_output_stream()

    def readable(self):
        return True

    def writable(self):
        return 'w' in self.mode

    def read(self, size=-1):
        if not self.readable():
            raise OSError("File is not readable")
        if size < 0:
            size = self.size
        return self.gin.read_bytes(size).get_data()

    def readall(self):
        return self.read(-1)

    def readinto(self, b):
        raise OSError("readinto() not supported on Gio.File objects")

    def readline(self, size=-1):
        raise OSError("readline() not supported on Gio.File objects")

    def readlines(self, hint=-1):
        raise OSError("readlines() not supported on Gio.File objects")

    def seek(self, offset, whence=os.SEEK_SET):
        self.gfd.seek(offset, GLib.SeekType.SET)

    def seekable(self):
        return True

    def tell(self):
        return self.gin.tell()

    def flush(self):
        pass

    def truncate(self, size=None):
        if size is None:
            size = self.tell()
        self.gfd.truncate(size)

    def fileno(self):
        raise OSError("fileno() called on Gio.File object")

    def isatty(self):
        return False

    def write(self, b):
        (res, count) = self.gout.write_all(b)
        if not res:
            raise OSError("write_all() failed")
        return count

    def writelines(self, lines):
        self.write(b"".join(lines))

    def close(self):
        self.flush()
        super().close()
        if self.gin:
            self.gin.close()
        if self.gout:
            self.gout.close()
        if self.gfd is not self.gin:
            self.gfd.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class GioFileSystem(object):
    def __init__(self):
        pass

    def safe(self, uri):
        if "://" not in uri:
            # assume local path
            uri = "file://" + urllib.parse.quote(uri)
        return uri

    def open(self, uri, mode='r'):
        return GioFileAdapter(Gio.File.new_for_uri(uri), mode)

    def join(self, base, url):
        if not base.endswith("/"):
            base += "/"
        return urllib.parse.urljoin(base, url)

    def basename(self, url):
        url = urllib.parse.urlparse(url)
        basename = os.path.basename(url.path)
        # Base name can be safely unquoted
        return urllib.parse.unquote(basename)

    def dirname(self, url):
        # dir name should not be unquoted. It could mess up the URI
        return os.path.dirname(url)
