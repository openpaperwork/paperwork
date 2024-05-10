import collections
import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps

import paperwork_backend.pageedit


LOGGER = logging.getLogger(__name__)
MODIFIER_ICONS = collections.defaultdict(
    lambda: "document-properties",
    {
        "color_equalization": (
            "paperwork_gtk.mainwindow.pageeditor", "magic_colors.png"
        ),
        "crop": "edit-cut-symbolic",
        "rotate_clockwise": "object-rotate-left-symbolic",
        "rotate_counterclockwise": "object-rotate-right-symbolic",
    }
)


class GtkPageEditorUI(paperwork_backend.pageedit.AbstractPageEditorUI):
    CAPABILITIES = (
        paperwork_backend.pageedit.AbstractPageEditorUI.CAPABILITY_SHOW_FRAME
    )

    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.core = plugin.core
        self.editor = None

        self.modifiers_to_toggles = {}
        self.buttons_to_modifiers = {}

        self.pil_img = None
        self.surface_img = None

        self.size_allocated = None
        self.allocate_handler_id = None

        self.draw_handler_id = self.plugin.widget_tree.get_object(
            "pageeditor_img"
        ).connect("draw", self.draw)

        self.zoom = self.plugin.widget_tree.get_object(
            "pageeditor_zoom_adjustment"
        )
        self.zoom.connect("value-changed", self._on_zoom_changed)

    def add_modifier_toggles(self):
        assert self.editor is not None

        toolbox = self.plugin.widget_tree.get_object("pageeditor_tools")
        zoom_box = self.plugin.widget_tree.get_object("pageeditor_zoom_box")
        for widget in list(toolbox.get_children()):
            if widget == zoom_box:
                continue
            toolbox.remove(widget)

        for modifier in self.editor.get_modifiers():
            glade = (
                "modifier_toggle.glade"
                if modifier['togglable'] else
                "modifier.glade"
            )
            modifier_widget_tree = self.core.call_success(
                "gtk_load_widget_tree",
                "paperwork_gtk.mainwindow.pageeditor", glade
            )

            button = modifier_widget_tree.get_object("pageeditor_modifier")
            button.set_tooltip_text(modifier['name'])
            if modifier['togglable']:
                button.set_active(modifier['enabled'])
                button.connect("toggled", self._on_modifier_changed)
                self.modifiers_to_toggles[modifier['id']] = button
            else:
                button.connect("clicked", self._on_modifier_changed)

            img = modifier_widget_tree.get_object("pageeditor_modifier_img")
            icon = MODIFIER_ICONS[modifier['id']]
            if isinstance(icon, tuple):
                icon = self.core.call_success("gtk_load_pixbuf", *icon)
                img.set_from_pixbuf(icon)
            else:
                img.set_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR)

            toolbox.pack_start(button, expand=False, fill=True, padding=0)

            self.buttons_to_modifiers[button] = modifier['id']

        if self.size_allocated is None:
            self.allocate_handler_id = self.plugin.widget_tree.get_object(
                "pageeditor_scroll"
            ).connect("size-allocate", self._on_size_allocate)
        else:
            self.set_default_zoom()

        self.plugin.widget_tree.get_object(
            "pageeditor_img"
        ).connect("realize", self.refresh)

    def _on_modifier_changed(self, button):
        modifier = self.buttons_to_modifiers[button]
        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_busy",)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.editor.on_modifier_selected(modifier))
        promise.then(self.refresh)
        promise.then(self.core.call_all, "on_idle")
        promise.schedule()

    def _on_size_allocate(self, *args, **kwargs):
        self.plugin.widget_tree.get_object(
            "pageeditor_scroll"
        ).disconnect(self.allocate_handler_id)
        self.allocate_handler_id = None

        self.set_default_zoom()

    def set_default_zoom(self, *args, **kwargs):
        allocation = self.plugin.widget_tree.get_object(
            "pageeditor_scroll"
        ).get_allocation()
        img_size = self.pil_img.size

        zoom = min(
            (allocation.width - 20) / img_size[0],
            (allocation.height - 20) / img_size[1]
        )
        LOGGER.info(
            "Allocation: %dx%d ; Image: %dx%d ==> Setting zoom at %f",
            allocation.width, allocation.height, img_size[0], img_size[1],
            zoom
        )
        self.zoom.set_value(zoom)
        self.refresh()

    def _get_scaled_image_size(self):
        img_size = self.pil_img.size
        zoom = self.zoom.get_value()
        return (img_size[0] * zoom, img_size[1] * zoom)

    def refresh(self, *args, **kwargs):
        widget_size = self._get_scaled_image_size()
        img = self.plugin.widget_tree.get_object("pageeditor_img")
        img.set_size_request(widget_size[0], widget_size[1])

        # WORKAROUND(JFlesch): I shouldn't have to use 'mainloop_schedule'
        # here. But somehow, I do have to use it :/
        self.core.call_all("mainloop_schedule", img.queue_resize)

    def _on_zoom_changed(self, adj=None):
        self.refresh()

    def set_modifier_state(self, modifier_id, enabled):
        super().set_modifier_state(modifier_id, enabled)
        LOGGER.info("Modifier %s: %s", modifier_id, enabled)

    def show_preview(self, img):
        super().show_preview(img)
        need_rezoom = (self.pil_img is None)

        self.pil_img = img
        self.surface_img = self.core.call_success(
            "pillow_to_surface", self.pil_img
        )

        if need_rezoom:
            self.set_default_zoom()

        self.refresh()
        LOGGER.info("Preview refreshed (%s)", img.size)

    def show_frame_selector(self):
        super().show_frame_selector()
        if self.pil_img is None:
            return
        img = self.plugin.widget_tree.get_object("pageeditor_img")
        self.core.call_all("draw_frame_stop", img)

        LOGGER.info(
            "show_frame_selector() (img size: %s ; frame: %s)",
            self.pil_img.size, self.editor.frame.get()
        )
        self.core.call_all(
            "draw_frame_start", img, self.pil_img.size,
            self.editor.frame.get, self.editor.frame.set
        )

    def hide_frame_selector(self):
        super().hide_frame_selector()
        LOGGER.info("hide_frame_selector()")
        img = self.plugin.widget_tree.get_object("pageeditor_img")
        self.core.call_all("draw_frame_stop", img)

    def on_edit_end(self, doc_url, page_idx):
        super().on_edit_end(doc_url, page_idx)
        self.plugin._on_edit_end(doc_url, page_idx)
        self._disconnect_draw()
        self.surface_img = None

    def _disconnect_draw(self):
        if self.draw_handler_id is None:
            return
        self.plugin.widget_tree.get_object(
            "pageeditor_img"
        ).disconnect(self.draw_handler_id)
        self.draw_handler_id = None

    def cancel(self):
        self.editor.on_cancel()
        self._disconnect_draw()

    def save(self):
        self.core.call_all("on_busy")
        self.plugin.widget_tree.get_object("pageeditor_back").set_sensitive(
            False
        )
        promise = openpaperwork_core.promise.Promise(self.core)
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.editor.on_save())
        promise = promise.then(self.core.call_all, "on_idle")
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_success(
            "transaction_simple_promise",
            [("upd", self.plugin.active_doc[0])]
        ))
        self.core.call_success("transaction_schedule", promise)

    def draw(self, widget, cairo_ctx):
        if self.surface_img is None:
            return
        cairo_ctx.save()
        try:
            zoom = self.zoom.get_value()
            cairo_ctx.scale(zoom, zoom)
            cairo_ctx.set_source_surface(self.surface_img.surface)
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.ui = None
        self.active_doc = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_page_editor',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_drawer_frame',
                'defaults': ['paperwork_gtk.drawer.frame'],
            },
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_zoomable',
                'defaults': ['paperwork_gtk.gesture.zoom'],
            },
            {
                'interface': 'page_editor',
                'defaults': ['paperwork_backend.pageedit.pageeditor'],
            },
            {
                'interface': 'pillow_to_surface',
                'defaults': ['paperwork_backend.cairo.pillow'],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.pageeditor", "pageeditor.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.widget_tree.get_object("pageeditor_cancel").connect(
            "clicked", self._on_cancel
        )
        self.widget_tree.get_object("pageeditor_back").connect(
            "clicked", self._on_apply
        )

        self.core.call_all(
            "on_zoomable_widget_new",
            self.widget_tree.get_object("pageeditor_scroll"),
            self.widget_tree.get_object("pageeditor_zoom_adjustment"),
        )

        self.core.call_all(
            "mainwindow_add", "right", "pageeditor", prio=0,
            header=self.widget_tree.get_object("pageeditor_header"),
            body=self.widget_tree.get_object("pageeditor_body")
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def doc_open(self, doc_id, doc_url):
        self._on_cancel(None)
        self.active_doc = (doc_id, doc_url)

    def gtk_open_page_editor(self, doc_id, doc_url, page_idx):
        LOGGER.info("Opening page editor on %s %d", doc_id, page_idx)
        self.active_doc = (doc_id, doc_url)

        page_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        if page_url is None:
            LOGGER.error(
                "Can't open page editor: Failed to get page url (%s, p%d)",
                doc_id, page_idx
            )
            return

        self.ui = GtkPageEditorUI(self)
        self.widget_tree.get_object("pageeditor_back").set_sensitive(True)

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_busy",)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_success, "page_editor_get", doc_url, page_idx,
            self.ui
        )
        promise = promise.then(
            self._show_page_editor, self.ui, doc_id, doc_url, page_idx
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_all, "on_idle")
        promise.schedule()

    def _on_cancel(self, button):
        if self.ui is None:
            return
        self.ui.cancel()
        self.ui = None

    def _on_apply(self, button):
        if self.ui is None:
            return
        self.ui.save()

    def _on_edit_end(self, doc_url, page_idx):
        self.core.call_success(
            "mainwindow_show", side="right", name="docview"
        )
        self.core.call_all("doc_reload", *self.active_doc)
        self.core.call_success(
            "mainloop_schedule", self.core.call_all, "doc_goto_page", page_idx
        )
        self.ui = None

    def _show_page_editor(self, page_editor, ui, doc_id, doc_url, page_idx):
        self.ui.editor = page_editor
        self.ui.add_modifier_toggles()
        self.core.call_all("mainwindow_show", "right", "pageeditor")
