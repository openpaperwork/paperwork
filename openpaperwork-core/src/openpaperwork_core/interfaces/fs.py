import abc


class Fs(abc.ABC):
    @abc.abstractmethod
    def fs_safe(self, uri):
        ...

    @abc.abstractmethod
    def fs_unsafe(self, uri):
        ...

    @abc.abstractmethod
    def fs_join(self, base, url):
        ...

    @abc.abstractmethod
    def fs_basename(self, url):
        ...

    @abc.abstractmethod
    def fs_dirname(self, url):
        ...

    @abc.abstractmethod
    def fs_hash(self, url):
        ...

    @abc.abstractmethod
    def fs_open(self, uri, mode='r', **kwargs):
        ...

    @abc.abstractmethod
    def fs_exists(self, uri):
        ...

    @abc.abstractmethod
    def fs_listdir(self, uri):
        ...

    @abc.abstractmethod
    def fs_rename(self, old_uri, new_uri):
        ...

    @abc.abstractmethod
    def fs_unlink(self, uri, **kwargs):
        ...

    @abc.abstractmethod
    def fs_rm_rf(self, uri, **kwargs):
        ...

    @abc.abstractmethod
    def fs_get_mtime(self, uri):
        ...

    @abc.abstractmethod
    def fs_getsize(self, uri):
        ...

    @abc.abstractmethod
    def fs_isdir(self, uri):
        ...

    @abc.abstractmethod
    def fs_copy(self, old_uri, new_uri):
        ...

    @abc.abstractmethod
    def fs_copytree(self, old_uri, new_uri):
        ...

    @abc.abstractmethod
    def fs_mkdir_p(self, uri):
        ...

    @abc.abstractmethod
    def fs_recurse(self, parent_uri, dir_included=False):
        ...

    @abc.abstractmethod
    def fs_hide(self, uri):
        ...

    @abc.abstractmethod
    def fs_get_mime(self, uri):
        ...

    @abc.abstractmethod
    def fs_iswritable(self, uri):
        ...

    @abc.abstractmethod
    def fs_resolve(self, uri):
        ...

    @abc.abstractmethod
    def fs_mktemp(
        self, prefix=None, suffix=None, mode='w+b', on_disk=False,
        **kwargs
    ):
        ...
