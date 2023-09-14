"""
openpaperwork_core.beacon contains everything related to the communication
with the website https://www.openpaper.work/
"""

import datetime
import logging


LOGGER = logging.getLogger(__name__)


class PeriodicTask(object):
    def __init__(
                self, config_section_name, min_delay: datetime.timedelta,
                periodic_callback, else_callback=lambda: None
            ):
        self.config_section_name = config_section_name
        self.min_delay = min_delay
        self.periodic_callback = periodic_callback
        self.else_callback = else_callback

    def register_config(self, core):
        setting = core.call_success(
            "config_build_simple", self.config_section_name,
            "last_run", lambda: datetime.date(year=1970, month=1, day=1)
        )
        core.call_all(
            "config_register", self.config_section_name + "_last_run", setting
        )

    def do(self, core):
        now = datetime.date.today()
        last_run = core.call_success(
            "config_get", self.config_section_name + "_last_run"
        )
        if hasattr(last_run, 'value'):
            # ConfigDate object from
            # openpaperwork_core.config.backend.configparser
            last_run = last_run.value
        LOGGER.info(
            "[%s] Last run: %s ; Now: %s",
            self.config_section_name, last_run, now
        )
        if now - last_run < self.min_delay:
            LOGGER.info(
                "[%s] Nothing to do (%s < %s)",
                self.config_section_name, now - last_run, self.min_delay
            )
            self.else_callback()
            return

        LOGGER.info(
            "[%s] Running %s (%s >= %s)",
            self.config_section_name,
            self.periodic_callback, now - last_run, self.min_delay
        )
        self.periodic_callback()

        LOGGER.info("[%s] Updating last run date", self.config_section_name)
        core.call_all(
            "config_put", self.config_section_name + "_last_run", now
        )
        core.call_all("config_save")
