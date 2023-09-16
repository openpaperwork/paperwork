import itertools
import json
import logging
import threading

try:
    import gi
    gi.require_version('Libinsane', '1.0')
    from gi.repository import GObject
    GI_AVAILABLE = True
except (ImportError, ValueError):
    GI_AVAILABLE = False

    # dummy so chkdeps can still be called
    class GObject(object):
        class GObject(object):
            pass

try:
    from gi.repository import Libinsane
    LIBINSANE_AVAILABLE = True
except (ImportError, ValueError):
    LIBINSANE_AVAILABLE = False

    # dummy so chkdeps can still be called
    class Libinsane(object):
        class LogLevel(object):
            DEBUG = 0
            INFO = 1
            WARNING = 2
            ERROR = 3

        class Logger(object):
            pass


import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from .. import _


LOGGER = logging.getLogger(__name__)
SCAN_ID_GENERATOR = itertools.count()

# Prevent closing or other operations on scanner and source instances when
# they are being used (scanning)
LOCK = threading.RLock()


class LibinsaneLogger(GObject.GObject, Libinsane.Logger):
    LEVELS = {
        Libinsane.LogLevel.DEBUG: LOGGER.debug,
        Libinsane.LogLevel.INFO: LOGGER.info,
        Libinsane.LogLevel.WARNING: LOGGER.warning,
        Libinsane.LogLevel.ERROR: LOGGER.error,
    }

    min_level = Libinsane.LogLevel.DEBUG

    def do_log(self, lvl, msg):
        if lvl < self.min_level:
            return
        self.LEVELS[lvl]("[LibInsane] " + msg)


def raw_to_img(params, img_bytes):
    fmt = params.get_format()
    assert fmt == Libinsane.ImgFormat.RAW_RGB_24
    w = params.get_width()
    h = int(len(img_bytes) / 3 / w)
    LOGGER.info(
        "raw_to_img(): w=%s, h=%d, len(img_bytes)=%d",
        w, h, len(img_bytes)
    )
    mode = "RGB"
    return PIL.Image.frombuffer(mode, (w, h), img_bytes, "raw", mode, 0, 1)


class ImageAssembler(object):
    MIN_CHUNK_SIZE = 64 * 1024

    def __init__(self, line_width):
        # 'Pieces' are pieces of the images that may or may not contain
        # full lines of pixels (or even partial pixel)

        # 'chunk': We want to provide the GUI with a preview of the scan.
        # To keep things simple, we provide chunk of the image and those
        # chunk must contain only entire lines of pixels.

        # and then we must also provide the whole image at the end.

        self.w = line_width  # in bytes

        self.current_piece = []
        self.all_chunks = []

    def add_piece(self, piece):
        self.current_piece.append(piece)
        lcurrent_piece = sum((len(c) for c in self.current_piece))
        if lcurrent_piece < self.w or lcurrent_piece < self.MIN_CHUNK_SIZE:
            return

        current_piece = b"".join(self.current_piece)
        chunkable = lcurrent_piece - (lcurrent_piece % self.w)
        new_chunk = current_piece[:chunkable]
        new_piece = current_piece[chunkable:]

        self.all_chunks.append(new_chunk)
        if len(new_piece) <= 0:
            self.current_piece = []
        else:
            self.current_piece = [new_piece]

    def get_last_chunk(self):
        if len(self.all_chunks) <= 0:
            return None
        return self.all_chunks[-1]

    def get_image(self):
        return b"".join(self.all_chunks) + b"".join(self.current_piece)


class Source(object):
    def __init__(self, core, scanner, source):
        self.core = core
        self.scanner = scanner
        self.source_id = source.get_name()
        self.source = source

    def __str__(self):
        return "{}:{}".format(str(self.scanner), self.source_id)

    def set_as_default(self):
        self.core.call_all(
            "config_put", "scanner_source_id", self.source_id
        )

    def _get_option(self, name):
        LOGGER.info(
            "Looking for possible values for option '%s' on %s"
            " : %s ...", name, str(self.scanner), self.source_id
        )
        options = self.source.get_options()
        options = {opt.get_name(): opt for opt in options}
        return options[name]

    def _get_opt_constraint(self, name):
        with LOCK:
            opt = self._get_option(name)
            constraint = opt.get_constraint()
            LOGGER.info(
                "%s : %s : %s : Possible values: %s",
                str(self.scanner), self.source_id, name, constraint
            )
            return constraint

    def get_modes(self):
        return self._get_opt_constraint('mode')

    def get_resolutions(self):
        return self._get_opt_constraint('resolution')

    def get_resolutions_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.get_resolutions
        )

    def set_default_resolution(self, resolution):
        self.core.call_all(
            "config_put", "scanner_resolution", int(resolution)
        )

    def scan(
                self, scan_id=None, resolution=None, max_pages=9999,
                close_on_end=False
            ):
        """
        Returns the source, the scan ID and an image generator
        """
        with LOCK:
            if scan_id is None:
                scan_id = next(SCAN_ID_GENERATOR)

            LOGGER.info("(id=%s) Setting scan options ...", scan_id)
            if resolution is None:
                resolution = self.core.call_success(
                    "config_get", "scanner_resolution"
                )
            mode = self.core.call_success("config_get", "scanner_mode")

            options = self.source.get_options()

            opts = {opt.get_name(): opt for opt in options}
            if 'resolution' in opts:
                opts['resolution'].set_value(resolution)
            if 'mode' in opts:
                try:
                    opts['mode'].set_value(mode)
                except Exception as exc:
                    LOGGER.warning(
                        "Failed to set scan mode", exc_info=exc
                    )
                    # will try to scan anyway

            extrasettings = self.core.call_success(
                "config_get", "scanner_extra_settings"
            )

            for (setting, value) in extrasettings.items():
                if setting in opts:
                    try:
                        opts[setting].set_value(value)
                    except Exception as exc:
                        LOGGER.warning(
                            "Failed to set scan setting %s=%s",
                            setting, value, exc_info=exc
                        )
                else:
                    LOGGER.warning("No such scanner setting: " + setting)

            imgs = self._scan(scan_id, resolution, max_pages, close_on_end)
            return (self, scan_id, imgs)

    def _scan(self, scan_id, resolution, max_pages, close_on_end=False):
        """
        Returns an image generator
        """
        # keep in mind that we are in a thread here, but listeners
        # must be called from the main loop
        LOGGER.info(
            "(id=%s) Scanning at resolution %d dpi ...",
            scan_id, resolution
        )

        has_started = False
        session = None
        try:
            page_nb = 0

            self.core.call_one(
                "mainloop_execute", self.core.call_all,
                "on_scan_feed_start", scan_id
            )
            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "on_progress", "scan", 0.0, _("Starting scan ...")
            )
            session = self.source.scan_start()

            while not session.end_of_feed() and page_nb < max_pages:
                self.core.call_success(
                    "mainloop_schedule", self.core.call_all,
                    "on_progress", "scan", 0.0,
                    _("Scanning page %d ...") % (page_nb + 1)
                )

                scan_params = session.get_scan_parameters()
                LOGGER.info(
                    "Expected scan parameters: %s ; %dx%d = %d bytes",
                    scan_params.get_format(),
                    scan_params.get_width(), scan_params.get_height(),
                    scan_params.get_image_size()
                )
                self.core.call_success(
                    "mainloop_schedule", self.core.call_all,
                    "on_scan_page_start", scan_id, page_nb, scan_params
                )

                assert (
                    scan_params.get_format()
                    == Libinsane.ImgFormat.RAW_RGB_24
                )
                image = ImageAssembler(scan_params.get_width() * 3)
                last_chunk = None
                nb_lines = 0
                total_lines = scan_params.get_height()
                buffer_size = (scan_params.get_width() * 3) + 1

                LOGGER.info("Scanning page %d/%d ...", page_nb, max_pages)
                while not session.end_of_page():
                    new_piece = session.read_bytes(buffer_size).get_data()

                    if not has_started:
                        # Mark the application as busy until we get the first
                        # read(). This is the only reliable time to be
                        # sure scanning is actually started.
                        self.core.call_success(
                            "mainloop_schedule", self.core.call_all,
                            "on_scan_started", scan_id
                        )
                        has_started = True

                    image.add_piece(new_piece)

                    chunk = image.get_last_chunk()
                    if chunk is not last_chunk:
                        last_chunk = chunk
                        pil = raw_to_img(scan_params, chunk)
                        nb_lines += pil.size[1]
                        progress = nb_lines / total_lines
                        if progress >= 1.0:
                            progress = 0.999
                        self.core.call_success(
                            "mainloop_schedule", self.core.call_all,
                            "on_progress", "scan", progress,
                            _("Scanning page %d ...") % (page_nb + 1)
                        )
                        self.core.call_success(
                            "mainloop_schedule", self.core.call_all,
                            "on_scan_chunk", scan_id, scan_params, pil
                        )

                LOGGER.info("Page %d/%d scanned", page_nb, max_pages)
                self.core.call_success(
                    "mainloop_schedule", self.core.call_all,
                    "on_progress", "scan", 0.999,
                    _("Scanning page %d ...") % (page_nb + 1)
                )
                img = raw_to_img(scan_params, image.get_image())
                yield img
                self.core.call_success(
                    "mainloop_schedule", self.core.call_all,
                    "on_scan_page_end", scan_id, page_nb, img
                )
                page_nb += 1
            LOGGER.info("End of feed")

            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "on_scan_feed_end", scan_id
            )
        finally:
            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "on_progress", "scan", 1.0
            )
            if session is not None:
                session.cancel()
            if close_on_end:
                self.close()

    def scan_promise(self, *args, scan_id=None, **kwargs):
        if scan_id is None:
            scan_id = next(SCAN_ID_GENERATOR)
        kwargs['scan_id'] = scan_id
        return (
            scan_id,
            openpaperwork_core.promise.ThreadedPromise(
                self.core, self.scan, args=args, kwargs=kwargs
            )
        )

    def close(self, *args, **kwargs):
        with LOCK:
            self.scanner.close()
            # return the args for convience when used with promises
            if len(args) == 1 and len(kwargs) == 0:
                return args
            return (args, kwargs)


class Scanner(object):
    def __init__(self, core, scanner):
        self.core = core
        self.dev_id = scanner.get_name()
        self.dev = scanner
        self.sources = None  # WORKAROUND(Jflesch): just to keep ref on them

    def __str__(self):
        return self.dev_id

    def __del__(self):
        if self.dev is not None:
            # Shouldn't happen.
            LOGGER.warning(
                "Scanner(%s, %s) is being garbage-collected",
                self.dev_id, id(self)
            )
        self.close()

    def close(self, *args, **kwargs):
        with LOCK:
            if self.dev is not None:
                LOGGER.info("Closing device %s (%s)", self.dev_id, id(self))
                self.dev.close()
                self.dev = None
            # return the args for convenience when used with promises
            if len(args) == 1 and len(kwargs) == 0:
                return args
            return (args, kwargs)

    def get_sources(self):
        with LOCK:
            LOGGER.info("Looking for scan sources on %s ...", self.dev_id)
            sources = self.dev.get_children()
            sources = [
                Source(self.core, self, source)
                for source in sources
            ]
            self.sources = {
                source.source_id: source
                for source in sources
            }
            LOGGER.info("%d sources found: %s", len(sources), sources)
            return self.sources

    def get_sources_promise(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.get_sources
        )

    def get_source(self, source_id):
        sources = self.get_sources()
        src = sources[source_id]
        return src

    def set_as_default(self):
        self.core.call_all(
            "config_put", "scanner_dev_id", 'libinsane:' + self.dev_id
        )


class BugReportCollector(object):
    def __init__(self, plugin, update_args):
        self.core = plugin.core
        self.plugin = plugin
        self.update_args = update_args

    def _notify(self, msg):
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "bug_report_update_attachment", "scanner",
            {"file_url": msg},
            *self.update_args
        )

    @staticmethod
    def _get_error_proof(func):
        try:
            r = func()
            if type(r) is bool or type(r) is int or type(r) is float:
                return r
            return str(r)
        except Exception as exc:
            return str(exc)

    def _collect_opt_info(self, opt, out: dict):
        out['name'] = self._get_error_proof(opt.get_name)
        out['title'] = self._get_error_proof(opt.get_title)
        out['description'] = self._get_error_proof(opt.get_desc)
        out['capabilities'] = self._get_error_proof(opt.get_capabilities)
        out['unit'] = self._get_error_proof(opt.get_value_unit)
        out['constraint_type'] = self._get_error_proof(opt.get_constraint_type)
        out['constraint'] = self._get_error_proof(opt.get_constraint)
        out['is_readable'] = self._get_error_proof(opt.is_readable)
        out['is_writable'] = self._get_error_proof(opt.is_writable)
        out['value'] = self._get_error_proof(opt.get_value)

    def _collect_item_info(self, item, base_name, out: dict):
        if item is None or item is False:
            out['reachable'] = False
            return

        out['reachable'] = True

        try:
            name = item.get_name()
            if base_name is not None and base_name != "":
                name = base_name + "/" + name
            self._notify(_("Examining %s") % name)
            out['name'] = item.get_name()
            out['options'] = {}
            out['children'] = {}

            options = item.get_options()
            for opt in options:
                out['options'][opt.get_name()] = {}
                self._collect_opt_info(opt, out['options'][opt.get_name()])

            children = item.get_children()
            for child in children:
                out['children'][child.get_name()] = {}
                self._collect_item_info(
                    child, name, out['children'][child.get_name()]
                )
        finally:
            item.close()

    def _write_scanners_info_to_tmp_file(self, infos):
        infos = json.dumps(
            infos, indent=4, separators=(",", ": "), sort_keys=True
        )
        (file_url, fd) = self.core.call_success(
            "fs_mktemp", prefix="scanner_", suffix=".json", mode="w",
            on_disk=True
        )
        with fd:
            fd.write(infos)
        return file_url

    @staticmethod
    def _collect_get_device(libinsane, dev_id):
        try:
            return libinsane.get_device(dev_id)
        except Exception as exc:
            LOGGER.error("Failed to get device [%s]", dev_id, exc_info=exc)
            return False  # can't return None or it will be ignored

    def _collect_all_info(self, scanners):
        out = {}
        promise = openpaperwork_core.promise.Promise(self.core)
        for dev in scanners:
            dev_id = dev[0]
            dev_name = dev[1]
            out[dev_id] = {
                'listing_name': dev_name
            }
            promise = promise.then(
                openpaperwork_core.promise.ThreadedPromise(
                    self.core, self._collect_get_device,
                    args=(self.plugin.libinsane, dev_id[len("libinsane:"):],)
                )
            )
            promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
                self.core, self._collect_item_info, args=("", out[dev_id],)
            ))
            promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, self._write_scanners_info_to_tmp_file, args=(out,)
            )
        )
        promise = promise.then(
            lambda file_url: self.core.call_all(
                "bug_report_update_attachment", "scanner", {
                    'file_url': file_url,
                    'file_size': self.core.call_success(
                        'fs_getsize', file_url
                    ),
                }, *self.update_args
            )
        )
        self.core.call_success("scan_schedule", promise)

    def run(self):
        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all,
            args=(
                "bug_report_update_attachment", "scanner",
                {"file_url": _("Getting scanner list ...")},
                *self.update_args
            )
        )
        promise = promise.then(self.plugin.scan_list_scanners_promise())
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self._collect_all_info
        ))
        self.core.call_success("scan_schedule", promise)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()

        # Looking for devices twice on Linux tends to crash ...
        self.devices_cache = []

        LOGGER.info("Initializing Libinsane ...")
        self.libinsane_logger = LibinsaneLogger()
        self.libinsane = None
        if LIBINSANE_AVAILABLE:
            Libinsane.register_logger(self.libinsane_logger)
            self.libinsane = Libinsane.Api.new_safebet()
            LOGGER.info(
                "Libinsane %s initialized", self.libinsane.get_version()
            )

        self._last_scanner = None

    def get_interfaces(self):
        return [
            "bug_report_attachments",
            "chkdeps",
            "scan",
            "stats",
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.core.call_all("work_queue_create", "scanner")

        settings = {
            'scanner_dev_id': self.core.call_success(
                "config_build_simple", "scanner",
                "dev_id", lambda: None
            ),
            'scanner_source_id': self.core.call_success(
                "config_build_simple", "scanner",
                "source", lambda: None
            ),
            'scanner_resolution': self.core.call_success(
                "config_build_simple", "scanner",
                "resolution", lambda: 300
            ),
            'scanner_mode': self.core.call_success(
                "config_build_simple", "scanner",
                "mode", lambda: "Color"
            ),
            'scanner_extra_settings': self.core.call_success(
                "config_build_simple", "scanner",
                "extrasettings", lambda: {}
            ),

        }
        for (k, setting) in settings.items():
            self.core.call_all(
                "config_register", k, setting
            )

    def chkdeps(self, out: dict):
        if not GI_AVAILABLE:
            out['gi'].update(openpaperwork_core.deps.GI)
        if not LIBINSANE_AVAILABLE:
            out['libinsane'] = {
                'debian': 'gir1.2-libinsane-1.0',
                'linuxmint': 'gir1.2-libinsane-1.0',
                'raspbian': 'gir1.2-libinsane-1.0',
                'ubuntu': 'gir1.2-libinsane-1.0',
            }

    def scan_schedule(self, promise):
        """
        Any promise or chain of promises related to scanners must *always*
        be run sequentially to avoid crashes. Otherwise, 2 threaded promises
        could run in parrallel. So other plugins using those promises should
        use scan_schedule() instead of mainloop_schedule()
        or promise.schedule().
        """
        self.core.call_success("work_queue_add_promise", "scanner", promise)
        return True

    def scan_list_scanners(self, *args, **kwargs):
        with LOCK:
            if len(self.devices_cache) > 0:
                return self.devices_cache

            LOGGER.info("Looking for scan devices ...")
            devs = self.libinsane.list_devices(
                Libinsane.DeviceLocations.ANY
            )
            devs = [
                # (id, human readable name)
                # prefix the IDs with 'libinsane:' so we know it comes from
                # our plugin and not another scan plugin
                (
                    'libinsane:' + dev.get_dev_id(),
                    "{} {}".format(
                        dev.get_dev_vendor(), dev.get_dev_model()
                    ),
                    dev.get_dev_vendor(),
                    dev.get_dev_model(),
                )
                for dev in devs
            ]
            devs.sort(key=lambda s: s[1])
            LOGGER.info("%d devices found: %s", len(devs), devs)
            self.devices_cache = devs
            return devs

    def scan_list_scanners_promise(self):
        """
        Return a promise for listing scanners.
        Must be started with "scan_schedule()", not "promise.schedule()" !
        """
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.scan_list_scanners
        )

    def scan_get_scanner(self, scanner_dev_id=None):
        if self._last_scanner is not None:
            self._last_scanner.close()
            self._last_scanner = None

        if scanner_dev_id is None:
            scanner_dev_id = self.core.call_success(
                "config_get", "scanner_dev_id"
            )
        if scanner_dev_id is None:
            return None

        if not scanner_dev_id.startswith("libinsane:"):
            return None
        scanner_dev_id = scanner_dev_id[len("libinsane:"):]

        with LOCK:
            LOGGER.info("Accessing scanner '%s' ...", scanner_dev_id)
            scanner = self.libinsane.get_device(scanner_dev_id)
            LOGGER.info("Scanner '%s' opened", scanner.get_name())
            self._last_scanner = Scanner(self.core, scanner)
            return self._last_scanner

    def scan_get_scanner_promise(self, scanner_dev_id=None):
        """
        Return a promise getting a scanner instance.
        Must be started with "scan_schedule()", not "promise.schedule()" !
        """
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.scan_get_scanner, args=(scanner_dev_id,)
        )

    def scan_promise(self, *args, source_id=None, **kwargs):
        """
        Return a promise that will run a scan.
        Must be started with "scan_schedule()", not "promise.schedule()" !
        """
        scanner_dev_id = self.core.call_success(
            "config_get", "scanner_dev_id"
        )
        if source_id is None:
            source_id = self.core.call_success(
                "config_get", "scanner_source_id"
            )
        if source_id is None:
            raise Exception("No source defined")
        scan_id = next(SCAN_ID_GENERATOR)

        promise = self.core.call_success(
            "scan_get_scanner_promise", scanner_dev_id
        )
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, Scanner.get_source, args=(source_id,)
            )
        )
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, Source.scan, args=(scan_id,), kwargs={
                    'close_on_end': True
                }
            )
        )

        return (scan_id, promise)

    def bug_report_get_attachments(self, out: dict):
        out['scanner'] = {
            'include_by_default': False,
            'date': None,
            'file_type': _("Scanner info."),
            'file_url': _("Select to generate"),
            'file_size': 0,
        }

    def on_bug_report_attachment_selected(self, attachment_id, *args):
        if attachment_id != 'scanner':
            return
        collector = BugReportCollector(self, args)
        collector.run()

    def stats_get(self, out: dict):
        if not LIBINSANE_AVAILABLE:
            out['libinsane_version'] = "not installed"
            return
        out['libinsane_version'] = Libinsane.Api.get_version()
