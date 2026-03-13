import logging
import math

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    CAIRO_AVAILABLE = False

from openpaperwork_core.interfaces.archives import FileArchives
from openpaperwork_core.interfaces.bug_report_attachment import BugReportAttachment
from openpaperwork_core.interfaces.bug_report_attachment import BugReportAttachmentSelectionListener
from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.uncaught_exception_listener import UncaughtExceptionListener
import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotListener
from openpaperwork_gtk import _


LOGGER = logging.getLogger(__name__)
SCREENSHOT_DATE_FORMAT = "%Y%m%d_%H%M_%S"
MAX_DAYS = 31
MAX_UNCAUGHT_EXCEPTION_SCREENSHOTS = 5


class Plugin(
    openpaperwork_core.PluginBase,
    BugReportAttachment,
    BugReportAttachmentSelectionListener,
    Chkdeps,
    GtkWindowListener,
    Screenshot,
    UncaughtExceptionListener,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=FileArchives,
                defaults=['openpaperwork_core.archives'],
            ),
            openpaperwork_core.Dependency(
                interface=Fs,
                defaults=[
                    'openpaperwork_core.fs.memory',
                    'openpaperwork_core.fs.python',
                ],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=["openpaperwork_gtk.mainloop.glib"],
            ),
            openpaperwork_core.Dependency(
                interface=ScreenshotListener,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.windows = []
        self.nb_uncaught = 0
        self.archiver = self.core.call_success(
            FileArchives.file_archive_get, storage_name="screenshots",
            file_extension="png"
        )

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'] = openpaperwork_core.deps.CAIRO

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _snap_screenshot(self, fd):
        image_size = (0, 0)

        for window in self.windows:
            if not window.is_drawable():
                LOGGER.warning("Window %s cannot be screenshoted", window)
            else:
                LOGGER.info("Screenshoting window %s", window)

        for window in self.windows:
            if not window.is_drawable():
                continue
            alloc = window.get_allocation()
            image_size = (
                max(image_size[0], alloc.width),
                image_size[1] + alloc.height
            )

        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, *image_size)
        cairo_ctx = cairo.Context(surface)

        for window in self.windows:
            if not window.is_drawable():
                continue
            alloc = window.get_allocation()
            window.draw(cairo_ctx)
            cairo_ctx.translate(0, alloc.height)

        surface.write_to_png(fd)

    def screenshot_snap_all_promise(self, temporary=True, name="screenshots"):
        if temporary:
            (file_url, fd) = self.core.call_success(
                Fs.fs_mktemp, prefix="{}_".format(name), suffix=".png",
                mode="wb", on_disk=True
            )
        else:
            file_url = self.archiver.get_new(name=name)
            fd = self.core.call_success(Fs.fs_open, file_url, mode='wb')

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=(ScreenshotListener.on_screenshot_before,)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_one, Mainloop.mainloop_execute,
            self._snap_screenshot, fd
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.catch(lambda *args, **kwargs: fd.close())
        promise = promise.then(fd.close)
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_all, ScreenshotListener.on_screenshot_after)
        promise = promise.then(lambda *args, **kwargs: None)

        return (file_url, promise)

    def screenshot_snap_widget(
                self, gtk_widget, out_file_url, margins=(20, 20, 20, 20),
                highlight=(0.67, 0.80, 0.93)
            ):
        assert out_file_url.endswith(".png")

        if not gtk_widget.is_drawable() or not gtk_widget.get_visible():
            LOGGER.warning(
                "%s is not visible. Cannot screenshot", gtk_widget
            )
            return None

        # find the GTK window of the widget
        window = gtk_widget.get_toplevel()
        if not window.is_drawable() or not window.get_visible():
            LOGGER.warning(
                "%s's window is not visible. Cannot screenshot",
                gtk_widget
            )
            return None

        # take a screenshot of the whole window
        win_alloc = window.get_allocation()
        win_surface = cairo.ImageSurface(
            cairo.FORMAT_RGB24, win_alloc.width, win_alloc.height
        )
        cairo_ctx = cairo.Context(win_surface)
        window.draw(cairo_ctx)

        widget_position = gtk_widget.translate_coordinates(window, 0, 0)
        widget_alloc = gtk_widget.get_allocation()

        # highlight
        if highlight is not None:
            cairo_ctx.save()
            try:
                cairo_ctx.new_path()
                border_width = 5
                margin = 5

                cairo_ctx.set_source_rgba(*highlight, 0.85)
                cairo_ctx.set_line_width(border_width)

                center = (
                    widget_position[0] + (widget_alloc.width / 2),
                    widget_position[1] + (widget_alloc.height / 2),
                )
                cairo_ctx.translate(*center)

                radius = (
                    (widget_alloc.width / 2) + (widget_alloc.height / 2)
                    + margin
                )
                if widget_alloc.width > widget_alloc.height:
                    scale = (1.0, widget_alloc.height / widget_alloc.width)
                else:
                    scale = (widget_alloc.width / widget_alloc.height, 1.0)

                cairo_ctx.scale(*scale)
                cairo_ctx.arc(0, 0, radius, 0, 2 * math.pi)
                cairo_ctx.scale(1.0 / scale[0], 1.0 / scale[1])
                cairo_ctx.stroke()
            finally:
                cairo_ctx.restore()

        # check it's visible enough
        start = (
            max(0, widget_position[0]),
            max(0, widget_position[1]),
        )
        size = (
            min(win_alloc.width - start[0], widget_alloc.width),
            min(win_alloc.height - start[1], widget_alloc.height),
        )
        if size[0] <= 15 or size[1] <= 15:
            LOGGER.warning(
                "%s is folded/hidden. Cannot screenshot", gtk_widget
            )
            return None

        # then cut it
        start = (
            max(0, widget_position[0] - margins[0]),
            max(0, widget_position[1] - margins[1])
        )
        size = (
            min(
                win_alloc.width - start[0],
                widget_alloc.width + margins[0] + margins[2]
            ),
            min(
                win_alloc.height - start[1],
                widget_alloc.height + margins[1] + margins[3],
            )
        )

        LOGGER.info(
            "Making screenshot of %s: %s (%s, %s)",
            gtk_widget, out_file_url, start, size
        )
        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, *size)
        cairo_ctx = cairo.Context(surface)
        cairo_ctx.translate(-start[0], -start[1])
        cairo_ctx.set_source_surface(win_surface)
        cairo_ctx.paint()

        with self.core.call_success(Fs.fs_open, out_file_url, "wb") as fd:
            surface.write_to_png(fd)
        return True

    def on_uncaught_exception(self, exc_info):
        self.nb_uncaught += 1
        if self.nb_uncaught > MAX_UNCAUGHT_EXCEPTION_SCREENSHOTS:
            # limit the number of screenshots in one session.
            return

        LOGGER.info("Uncaught exception. Taking screenshots")
        (_, promise) = self.screenshot_snap_all_promise(
            name="uncaught_exception_screenshots"
        )
        promise.schedule()

    def bug_report_get_attachments(self, out: dict):
        for (date, file_url) in self.archiver.get_archived():
            out[file_url] = {
                'date': date,
                'include_by_default': False,
                'file_type': _("App. screenshots"),
                'file_url': file_url,
                'file_size': self.core.call_success(Fs.fs_getsize, file_url),
            }

        out['screenshot_now'] = {
            'include_by_default': False,
            'date': None,
            'file_type': _("App. screenshots"),
            'file_url': _("Select to generate"),
            'file_size': 0,
        }

    def _update_attachment(self, file_url, *args):
        self.core.call_all(
            "bug_report_update_attachment", "screenshot_now", {
                "file_url": file_url,
                "file_size": self.core.call_success(Fs.fs_getsize, file_url),
            }, *args
        )

    def on_bug_report_attachment_selected(self, attachment_id, *args):
        if attachment_id != 'screenshot_now':
            return
        (file_url, promise) = self.screenshot_snap_all_promise(temporary=True)
        promise = promise.then(self._update_attachment, file_url, *args)
        promise.schedule()

    @openpaperwork_core.noop
    def on_bug_report_attachment_unselected(self, attachment_id, *args):
        pass
