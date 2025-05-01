import itertools

import PIL.Image

from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend.interfaces.scan import (
    AbstractScanner,
    AbstractSource,
    Scan,
    ScanListener
)


SCAN_ID_GENERATOR = itertools.count()


class Source(AbstractSource):
    def __init__(self, core, scanner, source_id):
        self.core = core
        self.scanner = scanner
        self.source_id = source_id

    def __str__(self):
        return "{}:{}".format(str(self.scanner), self.source_id)

    def set_as_default(self):
        raise NotImplementedError()

    def get_resolutions_promise(self):
        def get_resolutions():
            return [25, 100, 200, 300, 400, 500, 600]
        return openpaperwork_core.promise.Promise(self.core, get_resolutions)

    def set_default_resolution(self, resolution):
        raise NotImplementedError()

    def scan(self, scan_id=None, resolution=None, max_pages=9999):
        if scan_id is None:
            scan_id = next(SCAN_ID_GENERATOR)

        test_chunk = PIL.Image.new("RGB", (100, 200), (171, 205, 239))
        test_page = PIL.Image.new("RGB", (200, 200), (171, 205, 239))

        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            ScanListener.on_scan_feed_start, scan_id
        )
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            ScanListener.on_scan_page_start,
            scan_id, 0,
            None,  # TODO(Jflesch): scan params
        )
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            ScanListener.on_scan_started,
            scan_id,
        )
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            ScanListener.on_scan_chunk,
            scan_id,
            None,  # TODO(Jflesch): scan_params
            test_chunk
        )
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            ScanListener.on_scan_chunk,
            scan_id,
            None,  # TODO(Jflesch): scan_params
            test_chunk
        )
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            ScanListener.on_scan_chunk,
            scan_id,
            None,  # TODO(Jflesch): scan_params
            test_chunk
        )
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            ScanListener.on_scan_page_end, scan_id, 0,
            test_page
        )
        self.core.call_one(
            Mainloop.mainloop_schedule, self.core.call_all,
            ScanListener.on_scan_feed_end, scan_id
        )
        return (self, scan_id, [test_page])

    def scan_promise(self, *args, scan_id=None, **kwargs):
        if scan_id is None:
            scan_id = next(SCAN_ID_GENERATOR)
        kwargs['scan_id'] = scan_id
        return (scan_id, openpaperwork_core.promise.ThreadedPromise(
            self.core, self.scan, args=args, kwargs=kwargs
        ))

    def close(self, *args, **kwargs):
        pass


class Scanner(AbstractScanner):
    def __init__(self, core, scanner_id):
        self.core = core
        self.dev_id = scanner_id

    def __str__(self):
        return self.dev_id

    def close(self, *args, **kwargs):
        pass

    def get_sources(self):
        return {
            "fake_source0": Source(self.core, self, "fake_source0"),
            "fake_source1": Source(self.core, self, "fake_source1"),
        }

    def get_sources_promise(self):
        return openpaperwork_core.promise.Promise(self.core, self.get_sources)

    def get_source(self, source_id):
        return self.get_sources()[source_id]

    def set_as_default(self):
        raise NotImplementedError()


class Plugin(
    openpaperwork_core.PluginBase,
    Scan,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': Mainloop,
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                "interface": ScanListener,
                "defaults": [],
                "optional": True,
            },
        ]

    def scan_list_scanners(self):
        return [
            ("fake:scanner0", "Super scanner #0"),
            ("fake:scanner1", "Super scanner #1"),
        ]

    def scan_list_scanners_promise(self):
        return openpaperwork_core.promise.Promise(self.core, self.scan_list_scanners)

    def scan_get_scanner(self, scanner_dev_id):
        if scanner_dev_id != "fake:scanner0" and scanner_dev_id != "fake:scanner1":
            return None
        return Scanner(self.core, scanner_dev_id)

    def scan_get_scanner_promise(self, scanner_dev_id):
        return openpaperwork_core.promise.Promise(
            self.core, self.scan_get_scanner, args=(scanner_dev_id,)
        )

    def scan_promise(self, *args, **kwargs):
        scan_id = next(SCAN_ID_GENERATOR)

        promise = self.scan_get_scanner_promise("fake:scanner0")
        promise = promise.then(
            openpaperwork_core.promise.Promise(
                self.core, Scanner.get_source, args=("fake_source0",)
            )
        )
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, Source.scan, args=(scan_id,)
            )
        )

        def close(args):
            (source, scan_id, imgs) = args
            source.close()
            return (source, scan_id, imgs)

        promise = promise.then(close)
        return (scan_id, promise)

    def scan_schedule(self, promise):
        promise.schedule()
        return True
