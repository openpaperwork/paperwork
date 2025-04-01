import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class _LogHandler(logging.Handler):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.log_level = logging.DEBUG
        self.formatter = logging.Formatter(Plugin.LOG_FORMAT)

    def emit(self, record):
        if self.plugin.console is None:
            return
        if record.levelno < self.log_level:
            return
        line = self.formatter.format(record)
        self.plugin.console.print(line)


class Plugin(openpaperwork_core.PluginBase):
    LOG_FORMAT = '[%(levelname)-6s] [%(name)-30s] %(message)s'
    LOG_LEVELS = {
        'none': logging.CRITICAL,
        'critical': logging.CRITICAL,
        'error': logging.ERROR,
        'warn': logging.WARN,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG,
    }

    @classmethod
    def get_interfaces(cls):
        return [
            'logs',
            'uncaught_exception_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'uncaught_exception',
                'defaults': ['openpaperwork_core.uncaught_exception'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.console = None

    def cmd_set_console(self, console):
        self.console = console

    def init_logs(self, app_name, default_log_level):
        self.log_handler = _LogHandler(self)
        logging.getLogger().addHandler(self.log_handler)

        lvl = self.LOG_LEVELS[default_log_level]
        self.log_handler.log_level = lvl
        if lvl > logging.INFO:
            # Never disable info level ; it may be used by other plugins
            lvl = logging.INFO
        logging.getLogger().setLevel(lvl)

    def on_uncaught_exception(self, exc_info):
        LOGGER.error("=== UNCAUGHT EXCEPTION ===", exc_info=exc_info)
        LOGGER.error("==========================")
