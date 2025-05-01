import logging

from openpaperwork_core.interfaces.config import Config
import openpaperwork_core
import openpaperwork_core.promise

from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_backend.interfaces.scan import Scan

from paperwork_gtk import _
from paperwork_gtk.interfaces.settings import GtkSettingsScannerSetting


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase, GtkSettingsScannerSetting):
    RECOMMENDED = 300

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            {
                'interface': Config,
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': Scan,
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
        ]

    def complete_scanner_settings(
            self, global_widget_tree, parent_widget_tree,
            list_scanner_promise):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.settings.scanner",
            "popover.glade"
        )

        selector = widget_tree.get_object("selector")

        # WORKAROUND(Jflesch): set_sensitive() doesn't appear to work on
        # GtkMenuButton --> we have to play with set_popover()

        def reset_popover():
            dev_id = self.core.call_success(Config.config_get, "scanner_dev_id")
            parent_widget_tree.get_object("scanner_resolution").set_popover(
                selector if dev_id is not None and dev_id != "" else None
            )

        reset_popover()
        self.core.call_all(
            Config.config_add_observer, "scanner_dev_id", reset_popover
        )

        selector.connect("show", self._on_show, widget_tree)

    def _on_show(self, popover, widget_tree):
        LOGGER.info("Scanner resolution selector is visible")

        widget_tree.get_object("settings_stack").set_visible_child_name(
            "spinner"
        )
        widget_tree.get_object("spinner").start()
        box = widget_tree.get_object("selector_box")
        for child in box.get_children():
            box.remove(child)

        dev_id = self.core.call_success(Config.config_get, "scanner_dev_id")
        if dev_id is None:
            # TODO(Jflesch): better display
            self._display_resolutions([], widget_tree)
            return
        promise = self.core.call_success(Scan.scan_get_scanner_promise, dev_id)
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self._collect_resolutions
        ))
        promise = promise.then(self._display_resolutions, widget_tree)
        promise = promise.catch(self._on_error, widget_tree)
        self.core.call_success(Scan.scan_schedule, promise)

    def _collect_resolutions(self, dev):
        resolutions = set()
        try:
            children = dev.dev.get_children()
            for child in children:
                opts = {o.get_name(): o for o in child.get_options()}
                if 'resolution' not in opts:
                    continue
                constraint = opts['resolution'].get_constraint()
                resolutions.update(constraint)
        finally:
            dev.close()
        LOGGER.info("Got resolutions: %s", resolutions)
        resolutions = list(resolutions)
        resolutions.sort()
        return resolutions

    def _display_resolutions(self, resolutions, widget_tree):
        widget_tree.get_object("spinner").stop()
        widget_tree.get_object("settings_stack").set_visible_child_name(
            "selector"
        )

        box = widget_tree.get_object("selector_box")
        radios = []
        for resolution in resolutions:
            radio = self.core.call_success(
                GtkResources.gtk_load_widget_tree, "paperwork_gtk.settings.scanner",
                "popover_box.glade"
            )
            radio = radio.get_object("radio")
            if resolution != self.RECOMMENDED:
                radio.set_label(_("{} dpi").format(resolution))
            else:
                radio.set_label(_("{} dpi (recommended)").format(resolution))
            box.pack_start(radio, expand=False, fill=True, padding=0)
            radios.append((resolution, radio))

        for (resolution, radio) in radios[1:]:
            radio.join_group(radios[0][1])

        active = self.core.call_success(Config.config_get, "scanner_resolution")
        for (resolution, radio) in radios:
            if active == resolution:
                radio.set_active(True)

        for (resolution, radio) in radios:
            radio.connect(
                "toggled", self._on_toggle, widget_tree, resolution
            )

    def _on_toggle(self, checkbox, widget_tree, resolution):
        LOGGER.info("Selected resolution: %d", resolution)
        widget_tree.get_object("selector").popdown()
        self.core.call_success(Config.config_put, "scanner_resolution", resolution)

    def _on_error(self, exc, widget_tree):
        LOGGER.error("Fail to get scanner resolutions", exc_info=exc)
        # TODO(Jflesch): better display
        widget_tree.get_object("spinner").stop()
        widget_tree.get_object("settings_stack").set_visible_child_name(
            "selector"
        )
