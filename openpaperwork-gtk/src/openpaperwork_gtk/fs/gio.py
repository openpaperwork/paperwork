import ctypes
import io
import logging
import os
import tempfile

try:
    from gi.repository import Gio
    from gi.repository import GLib
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core.deps
import openpaperwork_core.fs


LOGGER = logging.getLogger(__name__)


class _GioFileAdapter(io.RawIOBase):
    def __init__(self, gfile, mode='r'):
        super().__init__()
        self.gfile = gfile
        self.mode = mode

        if 'w' in mode and 'r' not in mode:
            self.size = 0
        elif ('w' in mode or 'a' in mode) and not gfile.query_exists():
            self.size = 0
        else:
            try:
                fi = gfile.query_info(
                    Gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                    Gio.FileQueryInfoFlags.NONE
                )
                self.size = fi.get_attribute_uint64(
                    Gio.FILE_ATTRIBUTE_STANDARD_SIZE
                )
            except GLib.GError as exc:
                LOGGER.warning("Gio.Gerror", exc_info=exc)
                raise IOError(str(exc))

        self.gfd = None
        self.gin = None
        self.gout = None

        if 'r' in mode and 'w' in mode:
            if gfile.query_exists():
                self.gfd = gfile.open_readwrite()
            else:
                # create_readwrite() doesn't seem to always work on
                # Windows+MSYS2
                self.gfd = gfile.create_readwrite(Gio.FileCreateFlags.PRIVATE)
            if 'w' in mode:
                self.gfd.seek(0, GLib.SeekType.SET)
                self.gfd.truncate(0)
            self.gin = self.gfd.get_input_stream()
            self.gout = self.gfd.get_output_stream()
        elif 'r' in mode:
            self.gfd = gfile.read()
            self.gin = self.gfd
        elif 'w' in mode or 'a' in mode:
            if 'w' in mode:
                self.gfd = gfile.replace(
                    None,  # etag
                    False,  # make_backup
                    Gio.FileCreateFlags.PRIVATE
                )
            elif 'a' in mode:
                self.gfd = gfile.append_to(
                    Gio.FileCreateFlags.PRIVATE
                )
            self.gout = self.gfd

    def readable(self):
        return True

    def writable(self):
        return 'w' in self.mode or 'a' in self.mode

    def read(self, size=-1):
        if not self.readable():
            raise OSError("File is not readable")
        if size <= 0:
            size = self.size
            if size <= 0:
                return b""
        assert size > 0
        return self.gin.read_bytes(size).get_data()

    def readall(self):
        return self.read(-1)

    def readinto(self, b):
        raise OSError("readinto() not supported on Gio.File objects")

    def readline(self, size=-1):
        raise OSError("readline() not supported on Gio.File objects")

    def readlines(self, hint=-1):
        LOGGER.warning("readlines() shouldn't be called on a binary file"
                       " descriptor. This is not cross-platform")
        return [(x + b"\n") for x in self.readall().split(b"\n")]

    def seek(self, offset, whence=os.SEEK_SET):
        whence = {
            os.SEEK_CUR: GLib.SeekType.CUR,
            os.SEEK_END: GLib.SeekType.END,
            os.SEEK_SET: GLib.SeekType.SET,
        }[whence]
        self.gfd.seek(offset, whence)

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
        if self.gout is not None and hasattr(self.gout, 'get_fd'):
            return self.gout.get_fd()
        if self.gin is not None and hasattr(self.gin, 'get_fd'):
            return self.gin.get_fd()
        raise io.UnsupportedOperation("fileno() on Gio.File unsupported")

    def isatty(self):
        return False

    def write(self, b):
        res = self.gout.write_all(b)
        if not res[0]:
            raise OSError("write_all() failed on {}: {}".format(
                self.gfile.get_uri(), res)
            )
        return res[1]

    def writelines(self, lines):
        self.write(b"".join(lines))

    def close(self):
        self.flush()
        super().close()
        if self.gin is not None and self.gin is not self.gfd:
            self.gin.close()
        if self.gout is not None and self.gout is not self.gfd:
            self.gout.close()
        if self.gfd:
            self.gfd.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class _GioUTF8FileAdapter(io.RawIOBase):
    def __init__(self, raw):
        super().__init__()
        self.raw = raw
        self.line_iterator = None

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

    def readlines(self, hint=-1):
        all = self.readall()
        if os.linesep != "\n":
            all = all.replace(os.linesep, "\n")
        lines = [(x + "\n") for x in all.split("\n")]
        if lines[-1] == "\n":
            return lines[:-1]
        return lines

    def readline(self, hint=-1):
        if self.line_iterator is None:
            self.line_iterator = (line for line in self.readlines(hint))
        try:
            return next(self.line_iterator)
        except StopIteration:
            return ''

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
            (line + os.linesep).encode("utf-8")
            for line in lines
        ]
        return self.raw.writelines(lines)

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class Plugin(openpaperwork_core.fs.CommonFsPluginBase):
    PRIORITY = 50

    def __init__(self):
        super().__init__()
        self.vfs = None
        if GLIB_AVAILABLE:
            self.vfs = Gio.Vfs.get_default()
        self.tmp_files = set()

    def get_interfaces(self):
        return super().get_interfaces() + ['chkdeps']

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def fs_open(self, uri, mode='r', needs_fileno=False, **kwargs):
        if needs_fileno:
            # On Windows, `Gio.[Unix]OutputStream.get_fd()` doesn't seem
            # to be available
            return

        f = self.vfs.get_file_for_uri(uri)
        if ('w' not in mode and 'a' not in mode):
            if self.fs_exists(uri) is None:
                return None
        try:
            raw = _GioFileAdapter(f, mode)
            if 'b' in mode:
                return raw
            return _GioUTF8FileAdapter(raw)
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError("fs_open({}, mode={}): {}".format(
                uri, mode, str(exc)
            ))

    def fs_exists(self, url):
        if not GLIB_AVAILABLE:
            return None

        try:
            f = self.vfs.get_file_for_uri(url)
            if not f.query_exists():
                # this file does not exist for us, but it does not mean
                # another implementation of the plugin interface 'fs'
                # cannot handle it
                return None
            return True
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_listdir(self, url):
        if not GLIB_AVAILABLE:
            return None

        try:
            f = self.vfs.get_file_for_uri(url)
            if not f.query_exists():
                return None
            children = f.enumerate_children(
                Gio.FILE_ATTRIBUTE_STANDARD_NAME, Gio.FileQueryInfoFlags.NONE,
                None
            )
            for child in children:
                child = f.get_child(child.get_name())
                yield child.get_uri()
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_rename(self, old_url, new_url):
        try:
            old = self.vfs.get_file_for_uri(old_url)
            new = self.vfs.get_file_for_uri(new_url)
            assert not old.equal(new)
            if not old.query_exists():
                return None
            old.move(new, Gio.FileCopyFlags.NONE)
            return True
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_unlink(self, url, trash=True, **kwargs):
        try:
            f = self.vfs.get_file_for_uri(url)
            if not f.query_exists():
                return None

            LOGGER.info("Deleting %s (trash=%s) ...", url, trash)

            if not trash:
                deleted = f.delete()
                if not deleted:
                    raise IOError("Failed to delete %s" % url)
                return None

            deleted = False
            try:
                deleted = f.trash()
                if not deleted:
                    LOGGER.warning(
                        "Failed to trash %s. Will try to delete it instead",
                        url
                    )
            except Exception as exc:
                LOGGER.warning("Failed to trash %s. Will try to delete it"
                               " instead", url, exc_info=exc)

            if deleted and self.fs_exists(url) is not None:
                deleted = False
                # WORKAROUND(Jflesch): It seems in Flatpak, f.trash()
                # returns True when it actually does nothing.
                LOGGER.warning(
                    "trash(%s) returned True but file wasn't trashed."
                    " Will try to deleting it instead", f.get_uri()
                )

            if not deleted:
                try:
                    deleted = f.delete()
                except Exception as exc:
                    LOGGER.warning("Failed to deleted %s", url, exc_info=exc)
            if not deleted:
                raise IOError("Failed to delete %s" % url)
            return True
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_rm_rf(self, url, trash=True, **kwargs):
        if self.fs_exists(url) is None:
            return None

        try:
            LOGGER.info("Deleting %s ...", url)
            f = self.vfs.get_file_for_uri(url)
            deleted = False
            if trash:
                try:
                    deleted = f.trash()
                    if not deleted:
                        LOGGER.warning(
                            "Failed to trash %s."
                            " Will try to delete it instead",
                            url
                        )
                except Exception as exc:
                    LOGGER.warning(
                        "Failed to trash %s (trash()=%s)."
                        " Will try to delete it instead",
                        url, trash, exc_info=exc
                    )

            if deleted and self.fs_exists(url) is not None:
                deleted = False
                # WORKAROUND(Jflesch): It seems in Flatpak, f.trash()
                # returns True when it actually does nothing.
                LOGGER.warning(
                    "trash(%s) returned True but file wasn't trashed."
                    " Will try to deleting it instead", url
                )

            if not deleted:
                self._rm_rf(f)
            LOGGER.info("%s deleted", url)
            return True
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def _rm_rf(self, gfile):
        try:
            to_delete = [
                f for f in self._recurse(
                    gfile, dir_included=True, follow_symlinks=False
                )
            ]
            # make sure to delete the parent directory last:
            to_delete.sort(reverse=True, key=lambda f: f.get_uri())
            for f in to_delete:
                if not f.delete():
                    raise IOError("Failed to delete %s" % f.get_uri())
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_get_mtime(self, url):
        try:
            f = self.vfs.get_file_for_uri(url)
            if not f.query_exists():
                raise IOError("File {} does not exist".format(str(url)))
            if os.name == "nt":
                # WORKAROUND(Jflesch):
                # On Windows+MSYS2, it seems Gio.File.query_info()
                # return always 0 for Gio.FILE_ATTRIBUTE_TIME_CHANGED.
                path = self.fs_unsafe(url)
                return int(os.stat(path).st_mtime)
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_TIME_CHANGED, Gio.FileQueryInfoFlags.NONE
            )
            r = fi.get_attribute_uint64(Gio.FILE_ATTRIBUTE_TIME_CHANGED)
            if int(r) != 0:
                return r
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)

    def fs_getsize(self, url):
        try:
            f = self.vfs.get_file_for_uri(url)
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_SIZE, Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_attribute_uint64(Gio.FILE_ATTRIBUTE_STANDARD_SIZE)
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_isdir(self, url):
        if not GLIB_AVAILABLE:
            return None

        try:
            f = self.vfs.get_file_for_uri(url)
            if not f.query_exists():
                return None
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_TYPE, Gio.FileQueryInfoFlags.NONE
            )
            if fi.get_file_type() == Gio.FileType.DIRECTORY:
                return True
            return None
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_copy(self, old_url, new_url):
        try:
            old = self.vfs.get_file_for_uri(old_url)
            new = self.vfs.get_file_for_uri(new_url)
            if new.query_exists():
                new.delete()
            old.copy(new, Gio.FileCopyFlags.ALL_METADATA)
            return new_url
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            return None

    def fs_mkdir_p(self, url):
        if not GLIB_AVAILABLE:
            return None

        try:
            f = self.vfs.get_file_for_uri(url)
            if not f.query_exists():
                if os.name == "nt":
                    # WORKAROUND(Jflesch): On Windows+MSYS2,
                    # Gio.File.make_directory_with_parents() raises
                    # a Gio.GError "Unsupported operation" (bug ?)
                    path = self.fs_unsafe(url)
                    os.makedirs(path, mode=0o700, exist_ok=True)
                    return True
                f.make_directory_with_parents()
        except GLib.GError as exc:
            LOGGER.warning("Gio.GError", exc_info=exc)
            raise IOError("fs_mkdir_p({}): {}".format(url, str(exc)))

        return True

    def _recurse(self, parent, dir_included=False, follow_symlinks=True):
        """
        Yield all the children (depth first), but not the parent.
        """
        try:
            children = parent.enumerate_children(
                (
                    Gio.FILE_ATTRIBUTE_STANDARD_NAME
                    + "," + Gio.FILE_ATTRIBUTE_STANDARD_IS_SYMLINK
                ),
                Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
                None
            )
        except GLib.GError:
            # assumes it's a file and not a directory
            yield parent
            return

        for child in children:
            name = child.get_name()
            if not follow_symlinks:
                is_symlink = child.has_attribute("standard::is-symlink")
                is_symlink = is_symlink and child.get_is_symlink()
                if is_symlink:
                    yield parent.get_child(name)
                    continue
            child = parent.get_child(name)
            try:
                for sub in self._recurse(
                        child, dir_included=dir_included,
                        follow_symlinks=follow_symlinks):
                    yield sub
            except GLib.GError:
                yield child

        if dir_included:
            yield parent

    def fs_recurse(self, parent_uri, dir_included=False):
        parent = self.vfs.get_file_for_uri(parent_uri)
        for f in self._recurse(parent, dir_included):
            yield f.get_uri()

    def fs_hide(self, uri):
        if os.name != 'nt':
            LOGGER.warning("fs_hide('%s') can only works on Windows", uri)
            return None
        filepath = self.fs_unsafe(uri)
        LOGGER.info("Hiding file: {}".format(filepath))
        ret = ctypes.windll.kernel32.SetFileAttributesW(
            filepath, 0x02  # hidden
        )
        if not ret:
            raise ctypes.WinError()
        return True

    def fs_get_mime(self, uri):
        if os.name == 'nt':
            # WORKAROUND(Jflesch):
            # Gio.File.query_info().get_content_type() returns crap on Windows
            # (for instance '.pdf' instead of 'application/pdf').
            return None

        gfile = self.vfs.get_file_for_uri(uri)
        info = gfile.query_info(
            "standard::content-type", Gio.FileQueryInfoFlags.NONE
        )
        return info.get_content_type()

    def fs_mktemp(self, prefix=None, suffix=None, mode='w+b', **kwargs):
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

    def fs_iswritable(self, url):
        try:
            f = self.vfs.get_file_for_uri(url)
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_ACCESS_CAN_WRITE,
                Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_attribute_boolean(
                Gio.FILE_ATTRIBUTE_ACCESS_CAN_WRITE
            )
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def on_quit(self):
        for tmp_file in self.tmp_files:
            try:
                os.unlink(tmp_file)
            except FileNotFoundError:
                pass
