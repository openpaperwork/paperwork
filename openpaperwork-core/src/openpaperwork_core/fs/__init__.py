import hashlib
import logging
import os
import pathlib
import urllib
import urllib.parse

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class CommonFsPluginBase(openpaperwork_core.PluginBase):
    def __init__(self):
        """
        Should be used only by sub-classes
        """
        super().__init__()

    def get_interfaces(self):
        return ['fs']

    @staticmethod
    def fs_safe(uri):
        """
        Make sure the specified URI is actually an URI and not a Unix path.
        Returns:
            - An URI
        """
        if isinstance(uri, pathlib.Path):
            return uri.as_uri()
        LOGGER.debug("safe: %s", uri)
        if uri[:2] == "\\\\" or "://" in uri:
            LOGGER.debug("safe: --> %s", uri)
            return uri
        return pathlib.Path(uri).as_uri()

    @staticmethod
    def fs_unsafe(uri):
        """
        Turn an URI into an Unix path, whenever possible.
        Shouldn't be used at all.
        """
        LOGGER.debug("unsafe: %s", uri)
        if "://" not in uri and uri[:2] != "\\\\":
            LOGGER.debug("unsafe: --> %s", uri)
            return uri
        if not uri.startswith("file://"):
            LOGGER.debug("unsafe: --> EXC")
            raise Exception("TARGET URI SHOULD BE A LOCAL FILE")
        uri = uri[len("file://"):]
        if os.name == 'nt' and uri[0] == '/':
            # for some reason, URIs on Windows start with
            # "file:///C:\..." instead of "file://C:\..."
            uri = uri[1:]
        uri = urllib.parse.unquote(uri)
        return uri

    # It seems urllib.parse.urljoin doesn't work any protocol. For instance,
    # it doesn't play nice with smb:// and davs://
    URLLIB_SUPPORTED_PROTOCOLS = {"http", "https", "file", "ftp"}

    def fs_join(self, base, url):
        if not base.endswith("/"):
            base += "/"
        protocol = base.split("://", 1)[0].lower()
        if protocol in self.URLLIB_SUPPORTED_PROTOCOLS:
            return urllib.parse.urljoin(base, url)
        return base + url

    def fs_basename(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        if path == "":
            path = parsed_url.hostname
        if path is None:
            return None
        basename = os.path.basename(path)
        # Base name can be safely unquoted
        return urllib.parse.unquote(basename)

    def fs_dirname(self, url):
        # dir name should not be unquoted. It could mess up the URI
        return os.path.dirname(url)

    def fs_hash(self, url):
        with self.core.call_success("fs_open", url, 'rb') as fd:
            content = fd.read()
        return int(hashlib.sha256(content).hexdigest(), 16)

    def fs_copy(self, origin_url, dest_url):
        """
        default generic implementation
        """
        with open(origin_url, 'rb') as fd:
            content = fd.read()
        with open(dest_url, 'wb') as fd:
            fd.write(content)
        return True
