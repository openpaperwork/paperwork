import faulthandler
import logging
import os

from .. import (_, PluginBase)
from openpaperwork_core.logs import UnixTimeStampLogFormatter


LOGGER = logging.getLogger(__name__)
LOG_DATE_FORMAT = "%Y%m%d_%H%M_%S"
MAX_DAYS = 31


class LogLine(object):
    def __init__(self, line):
        self.line = line
        self.next = None


class LogHandler(logging.Handler):
    LOG_FORMAT = '%(asctime)s [%(levelname)-6s] [%(name)-30s] %(message)s'
    MAX_LINES = 5000
    MAX_UNCAUGHT_LOGGUED = 20

    def __init__(self, core, archiver):
        super().__init__()
        self.core = core
        self.archiver = archiver

        self.first_line = None
        self.last_line = None
        self.nb_lines = 0

        self.nb_uncaught_loggued = 0

        self.out_file_url = self.archiver.get_new()
        self.formatter = UnixTimeStampLogFormatter(self.LOG_FORMAT)
        self.out_fd = self.core.call_success(
            "fs_open", self.out_file_url, 'w',
            needs_fileno=True
        )
        faulthandler.disable()
        faulthandler.enable(file=self.out_fd)

    def emit(self, record):
        try:
            line = self.formatter.format(record) + "\n"
        except UnicodeDecodeError as exc:
            print(f"WARNING: {__file__}: UnicodeDecodeError: {repr(exc)}")
            return
        self.out_fd.write(line)

        line = LogLine(line)
        if self.last_line is not None:
            self.last_line.next = line
        self.last_line = line

        if self.first_line is None:
            self.first_line = line

        if self.nb_lines >= self.MAX_LINES:
            self.last_line = self.last_line.next
        else:
            self.nb_lines += 1

    def log_uncaught_exception(self):
        if self.nb_uncaught_loggued >= self.MAX_UNCAUGHT_LOGGUED:
            # avoid logging too much
            return

        self.nb_uncaught_loggued += 1

        out_file_url = self.archiver.get_new(
            name="uncaught_exception_logs"
        )
        self.formatter = logging.Formatter(self.LOG_FORMAT)

        with self.core.call_success("fs_open", out_file_url, 'w') as fd:
            line = self.first_line
            while line is not None:
                fd.write(line.line)
                line = line.next


class Plugin(PluginBase):
    PRIORITY = -10000

    def __init__(self):
        super().__init__()
        logging.getLogger().setLevel(logging.INFO)
        self.archiver = None

    def get_interfaces(self):
        return [
            'bug_report_attachments',
            'log_archiver',
            'uncaught_exception_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'file_archives',
                'defaults': ['openpaperwork_core.archives'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': 'uncaught_exception',
                'defaults': ['openpaperwork_core.uncaught_exception'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.archiver = self.core.call_success(
            "file_archive_get", storage_name="logs", file_extension="txt"
        )
        self.log_handler = LogHandler(core, self.archiver)
        logging.getLogger().addHandler(self.log_handler)

    def on_uncaught_exception(self, exc_info):
        self.log_handler.log_uncaught_exception()

    def bug_report_get_attachments(self, inputs: dict):
        archived = list(self.archiver.get_archived())
        archived.sort(key=lambda x: x[0], reverse=True)

        for (nb, (date, file_url)) in enumerate(archived):
            inputs[file_url] = {
                'date': date,
                # Users tend to send only the pre-selected elements in the bug
                # reports. However, when they report a sudden crash, we need
                # the logs of the previous session, not just the current one.
                # --> Include the logs of the last 2 previous sessions too.
                'include_by_default': nb <= 2,
                'file_type': _("Log file"),
                'file_url': file_url,
                'file_size': self.core.call_success("fs_getsize", file_url),
            }

        LOGGER.info("Flushing logs to disk")
        self.log_handler.out_fd.flush()
        os.fsync(self.log_handler.out_fd.fileno())
        file_url = self.log_handler.out_file_url
        inputs[file_url] = {
            'date': None,  # now
            'include_by_default': True,
            'file_type': _("Log file"),
            'file_url': file_url,
            'file_size': self.core.call_success("fs_getsize", file_url),
        }
