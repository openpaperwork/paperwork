import datetime
import logging
import os
import os.path
import sys
import tempfile

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


g_tmp_file = None


def _get_tmp_file():
    global g_tmp_file

    if g_tmp_file is not None:
        return g_tmp_file

    date = datetime.datetime.now()
    date = date.strftime("%Y%m%d_%H%M_%S")
    t = tempfile.NamedTemporaryFile(
        mode='w',
        suffix=".txt",
        prefix="openpaperwork_{}_".format(date),
        encoding='utf-8'
    )
    sys.stderr.write("Temporary file = {}\n".format(t.name))
    g_tmp_file = t
    return t


class _LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_level = logging.DEBUG
        self.formatter = logging.Formatter(Plugin.DEFAULT_LOG_FORMAT)
        self.out_fds = set()
        self.out_fds.add(sys.stderr)

    def emit(self, record):
        if record.levelno < self.log_level:
            return
        line = self.formatter.format(record)
        for fd in self.out_fds:
            fd.write(line + "\n")


class Plugin(PluginBase):
    CONFIG_FILE_SEPARATOR = ","

    DEFAULT_LOG_FILES = 'stderr'
    DEFAULT_LOG_FORMAT = '[%(levelname)-6s] [%(name)-30s] %(message)s'

    LOG_LEVELS = {
        'none': logging.CRITICAL,
        'critical': logging.CRITICAL,
        'error': logging.ERROR,
        'warn': logging.WARN,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG,
    }
    SPECIAL_FILES = {
        'stdout': lambda: sys.stdout,
        'stderr': lambda: sys.stderr,
        'temp': _get_tmp_file,
    }

    def __init__(self):
        super().__init__()
        self.log_file_paths = set()
        self.log_handler = None

    def get_interfaces(self):
        return [
            'logs',
            'uncaught_exception_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'uncaught_exception',
                'defaults': ['openpaperwork_core.uncaught_exception'],
            },
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
        ]

    def init_logs(self, app_name, default_log_level):
        self._fix_std('stdout')
        self._fix_std('stderr')

        section_name = "logging:" + app_name

        s = self.core.call_success(
            "config_build_simple", section_name, "level",
            lambda: default_log_level
        )
        self.core.call_all("config_register", "log_level", s)
        self.core.call_all(
            'config_add_observer', "log_level", self._reload_config
        )

        s = self.core.call_success(
            "config_build_simple", section_name, "files",
            lambda: self.DEFAULT_LOG_FILES
        )
        self.core.call_all("config_register", "log_files", s)
        self.core.call_all(
            'config_add_observer', "log_files", self._reload_config
        )

        s = self.core.call_success(
            "config_build_simple", section_name, "format",
            lambda: self.DEFAULT_LOG_FORMAT
        )
        self.core.call_all("config_register", "log_format", s)
        self.core.call_all(
            'config_add_observer', "log_format", self._reload_config
        )

        self.log_handler = _LogHandler()
        logging.getLogger().addHandler(self.log_handler)

        self._reload_config()

    def _fix_std(self, std_stream_name: str):
        if getattr(sys, std_stream_name, None) is not None:
            return
        # When frozen, sys.stderr / sys.stdout == None which is a problem
        if os.path.exists("/dev/null"):
            std_stream = open("/dev/null", "w")  # Linux / MacOS
        else:
            std_stream = open("NULL", "w")  # Windows
        setattr(sys, std_stream_name, std_stream)

    def _disable_logging(self):
        for fd in self.log_handler.out_fds:
            if fd != sys.stdout and fd != sys.stderr and fd != g_tmp_file:
                fd.close()
        self.log_handler.out_fds = set()

    def _enable_logging(self):
        self.log_handler.out_fds = set()
        first = None
        for file_path in self.log_file_paths:
            if file_path.lower() not in self.SPECIAL_FILES:
                fd = open(file_path, 'a')
                self.log_handler.out_fds.add(fd)
            else:
                fd = self.SPECIAL_FILES[file_path.lower()]()
                self.log_handler.out_fds.add(fd)
            if first is None and fd is not None:
                first = fd

    def _reload_config(self, *args, **kwargs):
        self._disable_logging()
        LOGGER.info("Reloading logging configuration")
        try:
            log_level = self.core.call_success('config_get', "log_level")
            self.set_log_level(log_level)
            self.log_file_paths = self.core.call_success(
                'config_get', "log_files",
            ).split(self.CONFIG_FILE_SEPARATOR)
            self.log_handler.formatter = logging.Formatter(
                self.core.call_success('config_get', "log_format")
            )
        finally:
            self._enable_logging()

    def set_log_level(self, log_level):
        lvl = self.LOG_LEVELS[log_level]
        self.log_handler.log_level = lvl
        if lvl > logging.INFO:
            # Never disable info level ; it may be used by other plugins
            lvl = logging.INFO
        logging.getLogger().setLevel(lvl)

    def on_uncaught_exception(self, exc_info):
        LOGGER.error("=== UNCAUGHT EXCEPTION ===", exc_info=exc_info)
        LOGGER.error("==========================")
