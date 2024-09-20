import datetime
import logging
import os
import re

import openpaperwork_core
import openpaperwork_core.beacon
import openpaperwork_core.promise

from .. import _version


LOGGER = logging.getLogger(__name__)

UPDATE_CHECK_INTERVAL = datetime.timedelta(days=7)
UPDATE_PATH = "/beacon/latest"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.periodic = None
        self.http = None

    def get_interfaces(self):
        return ["update_detection"]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'http_json',
                'defaults': ['openpaperwork_core.http.client'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def _register_config(self, core):
        setting = self.core.call_success(
            "config_build_simple", "update",
            "enabled", lambda: False
        )
        self.core.call_all(
            "config_register", "check_for_update", setting
        )
        setting = self.core.call_success(
            "config_build_simple", "update",
            "last_update_found", lambda: _version.version
        )
        self.core.call_all(
            "config_register", "last_update_found", setting
        )

    def _parse_version(self, version):
        version = re.split('[^0-9]', version)[:3]
        version = tuple([
            int(x.strip())
            for x in version
            if x.strip() != ''
        ])
        return version

    def update_check(self):
        LOGGER.info("Looking for updates...")

        def on_success(update_data, core):
            latest_version = update_data['paperwork'][os.name]
            LOGGER.info("Version advertised: %s", latest_version)
            self.core.call_all(
                "config_put", "last_update_found", latest_version
            )
            self.core.call_all("config_save")
            self.update_compare()

        promise = openpaperwork_core.promise.Promise(self.core, lambda: "")
        promise = promise.then(self.http.get_request_promise(UPDATE_PATH))
        promise = promise.then(on_success, self.core)
        promise = promise.catch(self._on_upd_check_error)
        promise.schedule()

    def _on_upd_check_error(self, exc):
        LOGGER.warning("Failed to look for update", exc_info=exc)

    def update_compare(self):
        remote_version = self.core.call_success(
            "config_get", "last_update_found"
        )
        remote_version = self._parse_version(remote_version)
        LOGGER.info("Remote version: %s", remote_version)
        local_version = self._parse_version(_version.version)
        LOGGER.info("Current version: %s", local_version)
        if remote_version > local_version:
            self.core.call_all(
                "on_update_detected", local_version, remote_version
            )

    def init(self, core):
        super().init(core)
        self.periodic = openpaperwork_core.beacon.PeriodicTask(
            "update",
            UPDATE_CHECK_INTERVAL,
            self.update_check,
            self.update_compare
        )
        self.http = self.core.call_success("http_json_get_client", "update")
        self._register_config(core)
        self.periodic.register_config(core)

        if self.core.call_success("config_get", "check_for_update"):
            self.core.call_all("mainloop_schedule", self.periodic.do, core)
