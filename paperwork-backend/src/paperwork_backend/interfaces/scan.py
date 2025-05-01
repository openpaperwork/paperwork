from typing import (
    List,
    Tuple
)
import abc


class AbstractSource(abc.ABC):
    @abc.abstractmethod
    def set_as_default(self):
        ...

    @abc.abstractmethod
    def get_resolutions_promise(self):
        ...

    @abc.abstractmethod
    def set_default_resolution(self, resolution):
        ...

    @abc.abstractmethod
    def scan(self, scan_id=None, resolution=None, max_pages=9999):
        ...

    @abc.abstractmethod
    def scan_promise(self, *args, scan_id=None, **kwargs):
        ...

    @abc.abstractmethod
    def close(self, *args, **kwargs):
        ...


class AbstractScanner(abc.ABC):
    @abc.abstractmethod
    def close(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def get_sources(self) -> List[AbstractSource]:
        ...

    @abc.abstractmethod
    def get_sources_promise(self):
        ...

    @abc.abstractmethod
    def get_source(self, source_id) -> AbstractSource:
        ...

    @abc.abstractmethod
    def set_as_default(self):
        ...


class Scan(abc.ABC):
    @abc.abstractmethod
    def scan_schedule(self, promise):
        ...

    @abc.abstractmethod
    def scan_list_scanners(self) -> Tuple[str, str]:
        ...

    @abc.abstractmethod
    def scan_list_scanners_promise(self):
        ...

    @abc.abstractmethod
    def scan_get_scanner(self, scanner_dev_id=None) -> AbstractScanner:
        ...

    @abc.abstractmethod
    def scan_get_scanner_promise(self, scanner_dev_id=None):
        ...

    @abc.abstractmethod
    def scan_promise(self, *args, source_id=None, **kwargs):
        ...


class ScanListener(abc.ABC):
    @abc.abstractmethod
    def on_scan_feed_start(self, scan_id):
        ...

    @abc.abstractmethod
    def on_scan_page_start(self, scan_id, page_nb, scan_params):
        ...

    @abc.abstractmethod
    def on_scan_started(self, scan_id):
        """
        Called when we actually get the first bytes from the scanner.
        Note that there may be a while between on_scan_feed_start(),
        on_scan_page_start() and on_scan_started().
        """
        ...

    @abc.abstractmethod
    def on_scan_chunk(self, scan_id, scan_params, img_chunk):
        ...

    @abc.abstractmethod
    def on_scan_page_end(self, scan_id, page_nb, img):
        ...

    @abc.abstractmethod
    def on_scan_feed_end(self, scan_id):
        ...
