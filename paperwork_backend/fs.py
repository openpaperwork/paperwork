#!/usr/bin/env python3

import io
import os
import urllib

from gi.repository import Gio
from gi.repository import GLib


class GioFileAdapter(io.RawIOBase):
    def __init__(self, gfile, mode='r'):
        super().__init__()
        self.gfile = gfile
        self.mode = mode

        fi = gfile.query_info(
            Gio.FILE_ATTRIBUTE_STANDARD_SIZE, Gio.FileQueryInfoFlags.NONE
        )
        self.size = fi.get_size()

        self.gfd = None
        self.gin = None
        self.gout = None

        if 'r' in mode:
            self.gin = self.gfd = gfile.read()
        elif 'w' in mode:
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


class GioUTF8FileAdapter(io.RawIOBase):
    def __init__(self, raw):
        super().__init__()
        self.raw = raw

    def readable(self):
        return self.raw.readable()

    def writable(self):
        return self.raw.writable()

    def read(self, *args, **kwargs):
        r = self.raw.read(*args, **kwargs)
        return r.decode("utf-8")

    def readall(self, *args, **kwargs):
        r = self.raw.readall(*args, **kwargs)
        return r.decode("utf-8")

    def readinto(self, *args, **kwargs):
        r = self.raw.readinto(*args, **kwargs)
        return r.decode("utf-8")

    def seek(self, *args, **kwargs):
        return self.raw.seek(*args, **kwargs)

    def seekable(self, seekable):
        return self.raw.seekable()

    @property
    def closed(self):
        return self.raw.closed

    def tell(self):
        # XXX(Jflesch): wrong ...
        return self.raw.tell()

    def flush(self):
        return self.raw.flush()

    def truncate(self, *args, **kwargs):
        # XXX(Jflesch): wrong ...
        return self.raw.truncate(*args, **kwargs)

    def fileno(self):
        return self.raw.fileno()

    def isatty(self):
        return self.raw.isatty()

    def write(self, b):
        b = b.encode("utf-8")
        return self.raw.write(b)

    def writelines(self, lines):
        lines = [
            line.encode("utf-8")
            for line in lines
        ]
        return self.raw.writelines(lines)

    def close(self):
        self.raw.close()

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

    def open(self, uri, mode='rb'):
        raw = GioFileAdapter(Gio.File.new_for_uri(uri), mode)
        if 'b' in mode:
            return raw
        return GioUTF8FileAdapter(raw)

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
