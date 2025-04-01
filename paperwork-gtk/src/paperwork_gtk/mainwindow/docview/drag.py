"""
When drag'n'dropping, enables the dragging-from-pages part.
"""

import logging

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)

TARGET_ENTRY_URI = 0


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -10000

    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'gtk_pageview',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'page_img',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.pages = []
        self.active_doc = None
        self.enabled = False

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def _enable_drag(self, widget, doc_id, doc_url, page_idx):
        widget.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK, [], Gdk.DragAction.MOVE
        )

        targets = Gtk.TargetList.new([])
        targets.add_uri_targets(TARGET_ENTRY_URI)
        widget.drag_source_set_target_list(targets)

        widget.drag_source_set_icon_name("document-send-symbolic")

        widget.connect(
            "drag-data-get", self._on_drag_data_get, doc_id, doc_url, page_idx
        )

    def _disable_drag(self, widget):
        widget.drag_source_unset()

    def _on_drag_data_get(
            self, widget, drag_context, data, info, time,
            doc_id, doc_url, page_idx):
        LOGGER.info("drag_data_get(%s, p%d, type=%d)", doc_id, page_idx, info)

        if info == TARGET_ENTRY_URI:
            # drag'n'drop API allows us to provide many URIs. But if we
            # do, applications like Firefox will try to display them all,
            # even if they don't understand the URI scheme.
            # --> we cheat and use the URI target for the extra info we may
            # need in Paperwork
            img_url = self.core.call_success(
                "page_get_img_url", doc_url, page_idx
            )
            if img_url is None:
                return
            img_url = img_url.split("#", 1)[0]
            img_url += "#doc_id={}&page={}".format(doc_id, page_idx)
            LOGGER.info("Img URL: {}".format(img_url))
            data.set_uris([img_url])
            return

        assert False

    def doc_open_components(self, out: list, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)
        self.pages = [p[1] for p in out]
        if self.enabled:
            for (visible, page) in out:
                if visible:
                    self._enable_drag(
                        page.widget, doc_id, doc_url, page.page_idx
                    )

    def on_layout_change(self, layout_name):
        enabled = (layout_name == 'grid')
        if enabled == self.enabled:
            return
        if enabled:
            LOGGER.info("Layout %s --> Enabling drag(-and-drop)", layout_name)
            for page in self.pages:
                self._enable_drag(page.widget, *self.active_doc, page.page_idx)
        else:
            LOGGER.info("Layout %s --> Disabling drag(-and-drop)", layout_name)
            for page in self.pages:
                self._disable_drag(page.widget)
        self.enabled = enabled
