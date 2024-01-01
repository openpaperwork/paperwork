from typing import Optional

import collections
import logging

try:
    from gi.repository import GLib  # noqa: F401
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import PIL
import PIL.Image
import PIL.ImageDraw

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.core = None
        self.stacks = None
        self.components = collections.defaultdict(dict)
        self.navigation_stacks = {'left': [], 'right': []}

        self.defaults = collections.defaultdict(list)  # keep track of the prio
        self.mainwindow = None
        self._mainwindow_size = None

    def get_interfaces(self):
        return [
            'app_actions',
            'app_shortcuts',
            'chkdeps',
            'gtk_mainwindow',
            'screenshot_provider',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio']
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_init',
                'defaults': ['openpaperwork_gtk.gtk_init'],
            },
            {
                'interface': 'icon',
                'defaults': ['paperwork_gtk.icon'],
            },
            {
                'interface': 'l10n_init',
                'defaults': ['paperwork_gtk.l10n'],
            },
            {
                'interface': 'screenshot',
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.core = core

        if not GTK_AVAILABLE:
            LOGGER.warning("not initializing main window without Gtk")
            return None

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow", "global.css"
        )

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.window", "mainwindow.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.window", "mainwindow.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        opt = self.core.call_success(
            "config_build_simple", "GUI", "main_window_size",
            lambda: (1024, 600)
        )
        self.core.call_all("config_register", "main_window_size", opt)
        main_win_size = self.core.call_success(
            "config_get", "main_window_size"
        )

        self.mainwindow = self.widget_tree.get_object("mainwindow")
        self.mainwindow.set_default_size(main_win_size[0], main_win_size[1])
        self.mainwindow.connect("destroy", self._on_mainwindow_destroy)
        self.mainwindow.connect(
            "size-allocate", self._on_mainwindow_size_allocate
        )

        try:
            self.mainwindow.set_icon_list([
                self.core.call_success("icon_get_pixbuf", "paperwork", 16),
                self.core.call_success("icon_get_pixbuf", "paperwork", 32),
                self.core.call_success("icon_get_pixbuf", "paperwork", 48),
                self.core.call_success("icon_get_pixbuf", "paperwork", 64),
                self.core.call_success("icon_get_pixbuf", "paperwork", 128),
            ])
        except KeyError as exc:
            # Will fail when generating data for the first time.
            LOGGER.warning("Failed to load main window icon", exc_info=exc)

        self.stacks = {
            "left": {
                "header": self.widget_tree.get_object(
                    "mainwindow_stack_header_left"
                ),
                "body": self.widget_tree.get_object(
                    "mainwindow_stack_body_left"
                ),
            },
            "right": {
                "header": self.widget_tree.get_object(
                    "mainwindow_stack_header_right"
                ),
                "body": self.widget_tree.get_object(
                    "mainwindow_stack_body_right"
                ),
            },
        }

        self.widget_tree.get_object("mainwindow_box_titlebar").connect(
            "notify::folded", self._on_titlebar_fold_change
        )
        self._on_titlebar_fold_change()

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_initialized(self):
        app = self.core.call_success("gtk_get_app")
        # when remote, this segfaults...
        if not app.get_is_remote():
            self.mainwindow.set_application(app)

        for side in self.defaults.keys():
            self.mainwindow_show_default(side)

        self.mainwindow.set_visible(True)
        self.core.call_all("on_gtk_window_opened", self.mainwindow)

    def on_quit(self):
        # needed to save window size
        # TODO(JFlesch): not really config --> should not be stored in config ?
        if self.mainwindow is not None:
            self.core.call_all("config_save")
            self.mainwindow.set_visible(False)

    def _on_titlebar_fold_change(self, *args, **kwargs):
        LOGGER.info("Main window fold has changed")
        self.core.call_all("on_mainwindow_fold_change")

    def mainwindow_get_folded(self):
        return self.widget_tree.get_object(
            "mainwindow_box_titlebar"
        ).get_folded()

    def _on_mainwindow_destroy(self, main_window):
        LOGGER.info("Main window destroy. Quitting")
        self.core.call_all("on_gtk_window_closed", self.mainwindow)
        self.core.call_all("mainloop_quit_graceful")

    def _on_mainwindow_size_allocate(self, main_win, rectangle):
        (w, h) = main_win.get_size()
        if self._mainwindow_size == (w, h):
            return
        self._mainwindow_size = (w, h)
        self.core.call_all("config_put", "main_window_size", (w, h))

    def mainwindow_get_main_container(self):
        return self.widget_tree.get_object("main_box")

    def mainwindow_add(self, side: str, name: str, prio: int, header, body):
        self.components[side][name] = {
            "header": header,
            "body": body,
        }
        components = self.components[side][name]
        stacks = self.stacks[side]
        for (position, widget) in components.items():
            if widget is None:
                continue
            stacks[position].add_named(widget, name)
        self.defaults[side].append((prio, name))
        self.defaults[side].sort(reverse=True)
        return True

    def mainwindow_show(self, side: str, name: Optional[str] = None):
        self.widget_tree.get_object(
            "mainwindow_box_titlebar"
        ).set_visible_child(
            self.stacks[side]['header']
        )
        self.widget_tree.get_object(
            "mainwindow_box_body"
        ).set_visible_child(
            self.stacks[side]['body']
        )

        if name is None:
            return False

        if name in self.navigation_stacks[side]:
            self.navigation_stacks[side].remove(name)
        self.navigation_stacks[side].append(name)
        return self._mainwindow_show(side)

    def _mainwindow_show(self, side: str):
        stacks = self.stacks[side]

        LOGGER.info("Navigation: %s", self.navigation_stacks[side])

        # some plugin give us None as component, which means to use
        # the previous component in the navigation stack (see doclist
        # in multiple selection mode)
        component_names = {h: None for h in stacks.keys()}
        for name in reversed(self.navigation_stacks[side]):
            LOGGER.info("Showing %s on %s", name, side)
            for (k, v) in self.components[side][name].items():
                if component_names[k] is None and v is not None:
                    component_names[k] = name
            if None not in component_names.values():
                break

        has_changed = False
        for (h, stack) in stacks.items():
            if h not in component_names or component_names[h] is None:
                continue
            if stack.get_visible_child_name() == component_names[h]:
                continue
            has_changed = True
            stack.set_visible_child_name(component_names[h])
        return has_changed

    def mainwindow_show_default(self, side: str):
        # the default component may be incomplete (for instance, it may
        # provide a header, but not a body). So we update the navigation
        # stack to make it the behaviour consistent:
        # We ensure it contains at least one element with all components
        # We respect priorities

        for (prio, name) in self.defaults[side]:
            self.navigation_stacks[side].append(name)
            if None not in self.components[side][name].values():
                break
        first = self.navigation_stacks[side].pop(0)
        self.navigation_stacks[side].reverse()

        self.core.call_all("mainwindow_show", side, first)

    def mainwindow_back(self, side: str):
        navigation_stack = self.navigation_stacks[side][:-1]
        self.navigation_stacks[side] = navigation_stack
        self._mainwindow_show(side)

    def app_actions_add(self, action):
        if self.mainwindow is not None:
            self.mainwindow.add_action(action)

    def mainwindow_focus(self):
        self.mainwindow.grab_focus()

    def mainwindow_present(self):
        if self.mainwindow is not None:
            self.mainwindow.present()
        else:
            LOGGER.warn("Activated a second time but mainwindow is None")

    def _draw_overlay(self, img, area, color):
        overlay = PIL.Image.new('RGBA', img.size, color + (0,))
        draw = PIL.ImageDraw.Draw(overlay)
        draw.rectangle(area, fill=color + (0x5F,))
        return PIL.Image.alpha_composite(img, overlay)

    def screenshot_snap_all_doc_widgets(self, out_dir):
        out = self.core.call_success("fs_join", out_dir, "main_window.png")
        self.core.call_success(
            "screenshot_snap_widget", self.mainwindow, out
        )

        left = self.stacks['left']['body']
        left_alloc = left.get_allocation()
        left_width = left_alloc.width
        (left_x, left_y) = left.translate_coordinates(self.mainwindow, 0, 0)
        left = left_x + left_width

        with self.core.call_success("fs_open", out, 'rb') as fd:
            img = PIL.Image.open(fd)
            img.load()
            img = img.convert("RGBA")

        img = self._draw_overlay(
            img, (0, 0, left, img.size[1]), (0, 0xFF, 0)
        )
        img = self._draw_overlay(
            img, (left, 0, img.size[0], img.size[1]), (0, 0, 0xFF)
        )

        # drop some black border in the scn
        img = img.crop(
            (left_x, left_x, img.size[0] - left_x, img.size[1] - left_x)
        )

        # keep only the top 150px
        img = img.crop((0, 0, img.size[0], min(300, img.size[1])))

        out = self.core.call_success(
            "fs_join", out_dir, "main_window_split.png"
        )
        with self.core.call_success("fs_open", out, 'wb') as fd:
            img.save(fd, format="PNG")

    def app_shortcut_add(
            self, shortcut_group, shortcut_desc, shortcut_keys, action_name):
        """
        Arguments:
           - shortcut_group: Group name in which this shortcut belongs
             (human readable, translated ; actually used in the shortcut window
             if enabled)
           - shortcut_desc: Describe the shortcut
             (human readable, translated ; actually used in the shortcut window
             if enabled)
           - shortcut_keys: see gtk_accelerator_parse()
           - action_name: GAction that must be triggered
        """
        if self.mainwindow is None or not GTK_AVAILABLE:
            return
        LOGGER.info("Keyboard shortcut: %s --> %s", shortcut_keys, action_name)
        Gtk.Application.get_default().set_accels_for_action(
            action_name, (shortcut_keys, None)
        )
