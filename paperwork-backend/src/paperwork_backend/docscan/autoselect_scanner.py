"""
Select a scanner if none has been selected yet or if the currently selected one
doesn't exist anymore.

IMPORTANT: This plugin must list the devices only if required. Otherwise
it tends to mess up some Sane backend like the Brother one for instance.
"""
import logging

from openpaperwork_core.interfaces.config import Config
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend.interfaces.scan import Scan
import paperwork_backend.util


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    Scan
):
    PRIORITY = 1000

    def __init__(self, core):
        super().__init__(core)
        self.allow_autoselect = True

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
        ]

    @openpaperwork_core.noop
    def scan_schedule(self, promise):
        pass

    @openpaperwork_core.noop
    def scan_list_scanners(self):
        pass

    @openpaperwork_core.noop
    def scan_list_scanners_promise(self):
        pass

    @openpaperwork_core.noop
    def scan_promise(self, *args, source_id=None, **kwargs):
        pass

    @openpaperwork_core.noop
    def scan_get_scanner(self, scanner_dev_id=None):
        if not self.allow_autoselect:
            # prevent self-calling
            return None

        self.allow_autoselect = False
        try:
            scanner = None
            if scanner_dev_id is None:
                scanner_dev_id = self.core.call_success(
                    Config.config_get, "scanner_dev_id"
                )
            try:
                if scanner_dev_id is not None:
                    scanner = self.core.call_success(
                        Scan.scan_get_scanner, scanner_dev_id
                    )
            except Exception as exc:
                # may happen if ID has changed (those containing the USB
                # bus + ID for instance)
                LOGGER.warning(
                    "Failed to get scanner '%s'."
                    " Will try to find the closest one",
                    scanner_dev_id, exc_info=exc
                )
            if scanner is not None:
                return scanner

            devs = self.core.call_success(Scan.scan_list_scanners)
            scanner_dev_id = self._find_dev_id(devs, scanner_dev_id)
            if scanner_dev_id is None:
                return None
            return self.core.call_success(Scan.scan_get_scanner, scanner_dev_id)
        finally:
            self.allow_autoselect = True

    def scan_get_scanner_promise(self, scanner_dev_id=None):
        """
        Overload the method 'scan_get_scanner_promise' to check whether
        the device actually exists, and if not find the closest one.
        """
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.scan_get_scanner, args=(scanner_dev_id,)
        )

    def _find_dev_id(self, devs, current_dev_id=None):
        devs = [dev[0] for dev in devs]
        LOGGER.info("Available scanners: %s", devs)

        if len(devs) <= 0:
            LOGGER.error("No scanner found !")
            return None
        elif current_dev_id is None:
            # pick a scanner at random.
            selected = devs[0]
        else:
            LOGGER.info("Previously selected scanner: %s", current_dev_id)
            # look for the closest scanner ID
            devs = [
                (
                    paperwork_backend.util.levenshtein_distance(
                        dev, current_dev_id
                    ),
                    dev
                )
                for dev in devs
            ]
            devs.sort()
            selected = devs[0][1]

        LOGGER.info("Selected scanner: %s", selected)
        # ASSUMPTION(Jflesch): we assume here the requested scanner was
        # the one selected in the configuration --> we update the configuration
        # to avoid listing devices every time.
        self.core.call_success(Config.config_put, "scanner_dev_id", selected)
        return selected
