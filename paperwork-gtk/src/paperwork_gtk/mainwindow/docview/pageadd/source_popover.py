import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_scan_buttons_popover',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_scan_buttons',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageadd.buttons'
                ],
            },
        ]

    def __init__(self, core):
        super().__init__(core)

        opt = self.core.call_success(
            "config_build_simple", "pageadd", "active_source", lambda: None
        )
        self.core.call_all("config_register", "pageadd_active_source", opt)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageadd", "source_popover.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

    def pageadd_sources_refresh(self):
        active = self.core.call_success("config_get", "pageadd_active_source")

        parent = self.widget_tree.get_object("page_sources_box")
        for child in parent.get_children():
            parent.remove(child)

        selectors = []
        self.core.call_all("pageadd_get_sources", selectors)
        for (selector, source_name, source_id, callback) in selectors[1:]:
            selector.join_group(selectors[0][0])
        for (selector, source_name, source_id, callback) in selectors:
            selector.connect(
                "toggled", self._on_toggle, source_name, source_id, callback
            )
            parent.pack_start(selector, expand=False, fill=True, padding=0)
        for (selector, source_name, source_id, callback) in selectors:
            if active == source_id:
                break
        else:
            active = None

        if active is None:
            if len(selectors) > 0:
                (selector, source_name, source_id, callback) = selectors[0]
                selector.set_active(True)
                self._on_toggle(selector, source_name, source_id, callback)
        else:
            for (selector, source_name, source_id, callback) in selectors:
                if active == source_id:
                    selector.set_active(True)
                    self._on_toggle(selector, source_name, source_id, callback)
                    break

        # if there is a single choice, there is no point in letting
        # the user choose. This is just confusing.
        self.core.call_all(
            "pageadd_buttons_set_source_popover",
            self.widget_tree.get_object("page_sources_popover")
            if len(selectors) > 1 else None
        )

    def _on_toggle(self, widget, source_name, source_id, callback):
        if not widget.get_active():
            return
        self.core.call_all(
            "pageadd_set_default_action", source_name, callback, source_id
        )
        self.core.call_all(
            "config_put", "pageadd_active_source", source_id
        )
