import datetime
import logging
import os
import re

import openpaperwork_core
import openpaperwork_core.beacon
import openpaperwork_core.promise

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.http_json import HttpJson
from openpaperwork_core.interfaces.mainloop import Mainloop
from paperwork_backend.interfaces.update_detection import UpdateDetection
from paperwork_backend.interfaces.update_detection import UpdateDetectionListener
import paperwork_backend._version


LOGGER = logging.getLogger(__name__)

UPDATE_CHECK_INTERVAL = datetime.timedelta(days=7)
UPDATE_PATH = "/beacon/latest"


class Plugin(
    openpaperwork_core.PluginBase,
    UpdateDetection,
):
    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=Config,
                defaults=['openpaperwork_core.config'],
            ),
            openpaperwork_core.Dependency(
                interface=HttpJson,
                defaults=['openpaperwork_core.http.client'],
            ),
            openpaperwork_core.Dependency(
                interface=Mainloop,
                defaults=['openpaperwork_gtk.mainloop.glib'],
            ),
            openpaperwork_core.Dependency(
                interface=UpdateDetectionListener,
                defaults=[],
                optional=True,
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.periodic = openpaperwork_core.beacon.PeriodicTask(
            "update",
            UPDATE_CHECK_INTERVAL,
            self.update_check,
            self.update_compare
        )
        self.http = self.core.call_success(HttpJson.http_json_get_client, "update")
        self._register_config(core)
        self.periodic.register_config(core)

        if self.core.call_success(Config.config_get, "check_for_update"):
            self.core.call_all(Mainloop.mainloop_schedule, self.periodic.do, core)

    def _register_config(self, core):
        setting = self.core.call_success(
            Config.config_build_simple, "update",
            "enabled", lambda: False
        )
        self.core.call_all(
            Config.config_register, "check_for_update", setting
        )
        setting = self.core.call_success(
            Config.config_build_simple, "update",
            "last_update_found", lambda: paperwork_backend._version.version
        )
        self.core.call_all(
            Config.config_register, "last_update_found", setting
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
                Config.config_put, "last_update_found", latest_version
            )
            self.core.call_all(Config.config_save)
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
            Config.config_get, "last_update_found"
        )
        remote_version = self._parse_version(remote_version)
        LOGGER.info("Remote version: %s", remote_version)
        local_version = self._parse_version(paperwork_backend._version.version)
        LOGGER.info("Current version: %s", local_version)
        if remote_version > local_version:
            self.core.call_all(
                UpdateDetectionListener.on_update_detected, local_version, remote_version
            )
