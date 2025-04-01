"""
This plugin requires pydbus.
If Pydbus is not installed. It just does nothing.
"""

import logging
import os
import socket
import time

try:
    import pydbus
    PYDBUS_AVAILABLE = True
except ImportError:
    PYDBUS_AVAILABLE = False

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    PRIORITY = 50

    @classmethod
    def get_interfaces(cls):
        return ['external_apps']

    @classmethod
    def get_deps(cls):
        return []

    def _get_file_manager_proxy(self):
        bus = pydbus.SessionBus()
        proxy = bus.get(
            "org.freedesktop.FileManager1",
            "/org/freedesktop/FileManager1"
        )
        iface = proxy['org.freedesktop.FileManager1']
        return iface

    def _open_url(self, func_name, url):
        if not PYDBUS_AVAILABLE:
            LOGGER.info("Pydbus is not available")
            return None
        try:
            uid = "{}{}_TIME{}".format(
                socket.gethostname(), os.getpid(), int(time.time())
            )
            iface = self._get_file_manager_proxy()
            LOGGER.info("Opening %s using Dbus", url)
            getattr(iface, func_name)([url], uid)
        except Exception as exc:
            LOGGER.error(
                "Failed to open %s using Dbus", url, exc_info=exc
            )
            return None
        return True

    def external_app_open_file(self, file_url):
        # doesn't really open the file, but close enough.
        return self._open_url('ShowItems', file_url)

    def external_app_open_folder(self, folder_url):
        return self._open_url('ShowFolders', folder_url)

    def external_app_can_send_as_attachment(self) -> None:
        return None

    def external_app_send_as_attachment(self, uri) -> None:
        return None
