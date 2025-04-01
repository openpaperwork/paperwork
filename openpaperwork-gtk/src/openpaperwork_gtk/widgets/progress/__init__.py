import logging
import math
import threading
import time

import openpaperwork_core
import openpaperwork_core.deps

try:
    import gi
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk
    GDK_AVAILABLE = True
except (ImportError, ValueError):
    GDK_AVAILABLE = False

NEEDS_ATTENTION_TIMEOUT = 2.1
LOGGER = logging.getLogger(__name__)
TIME_BETWEEN_UPDATES = 0.3

# Tasks are often chained one after the other. We don't want the button/popover
# to disappear and reappear continually. So when a task ends, we
# give them some extra time to live.
# STAY_ALIVES is the number of updates we wait before hiding them.
STAY_ALIVES = int(2.0 / TIME_BETWEEN_UPDATES)


class ProgressWidget(object):
    def __init__(self, core):
        self.core = core
        self.widget = None

        # A thread updates the widgets every 300ms. We don't update them
        # each time on_progress() is called to not degrade performanes
        self.thread = None
        self.lock = threading.RLock()
        self.progress_widget_trees = {}
        # self.progresses is only used to transmit new progress updates
        # to the thread
        self.progresses = {}
        self.button_widget_tree = None
        self.details_widget_tree = None

        self.stay_alives = STAY_ALIVES

        self.button_widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "openpaperwork_gtk.widgets.progress",
            "progress_button.glade"
        )
        if self.button_widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return
        self.details_widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "openpaperwork_gtk.widgets.progress",
            "progress_popover.glade"
        )
        if self.details_widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.button_widget_tree.get_object("progress_button").set_popover(
            self.details_widget_tree.get_object(
                "progresses_popover"
            )
        )
        self.button_widget_tree.get_object("progress_icon").connect(
            "draw", self._on_icon_draw
        )

        self.widget = self.button_widget_tree.get_object("progress_revealer")

    def needs_attention(self):
        button = self.button_widget_tree.get_object("progress_button")
        button.get_style_context().add_class("progress_button_needs_attention")
        self.core.call_success(
            "mainloop_schedule",
            button.get_style_context().remove_class,
            "progress_button_needs_attention",
            delay_s=NEEDS_ATTENTION_TIMEOUT
        )

    def _thread(self):
        self.stay_alives = STAY_ALIVES
        while self.thread is not None:
            time.sleep(TIME_BETWEEN_UPDATES)
            self.core.call_one(
                "mainloop_execute", self._upd_progress_widgets
            )

    def _upd_progress_widgets(self):
        with self.lock:
            for (upd_type, (progress, description)) in self.progresses.items():
                self._upd_progress_widget(
                    upd_type, progress, description
                )
            self.progresses = {}

            if len(self.progress_widget_trees) > 0:
                self.stay_alives = STAY_ALIVES
                return

            if self.stay_alives > 0:
                self.stay_alives -= 1
                return

            self.button_widget_tree.get_object(
                "progress_revealer"
            ).set_reveal_child(False)
            self.thread = None
            return

    def _upd_progress_widget(self, upd_type, progress, description):
        if progress >= 1.0:  # deletion of progress
            if upd_type not in self.progress_widget_trees:
                LOGGER.warning(
                    "Got 2 notifications of end of task for '%s'",
                    upd_type
                )
                return
            LOGGER.info("Task '%s' has ended", upd_type)
            widget_tree = self.progress_widget_trees.pop(upd_type)
            box = self.details_widget_tree.get_object(
                "progresses_box"
            )
            details = widget_tree.get_object("progress_bar")
            box.remove(details)
            details.unparent()
            self.button_widget_tree.get_object("progress_button").queue_draw()
            self.needs_attention()

            LOGGER.info(
                "Task '%s' has ended (%d remaining)",
                upd_type, len(self.progress_widget_trees)
            )
            return

        if upd_type not in self.progress_widget_trees:  # creation of progress
            LOGGER.info(
                "Task '%s' has started (%d already active)",
                upd_type, len(self.progress_widget_trees)
            )
            widget_tree = self.core.call_success(
                "gtk_load_widget_tree",
                "openpaperwork_gtk.widgets.progress",
                "progress_details.glade"
            )
            box = self.details_widget_tree.get_object(
                "progresses_box"
            )
            box.add(widget_tree.get_object("progress_bar"))
            self.progress_widget_trees[upd_type] = widget_tree
            self.needs_attention()
        else:
            widget_tree = self.progress_widget_trees[upd_type]

        # update of progress
        progress_bar = widget_tree.get_object("progress_bar")
        progress_bar.set_fraction(progress)
        progress_bar.set_text(description if description is not None else "")

        self.button_widget_tree.get_object("progress_button").queue_draw()

        self.button_widget_tree.get_object(
            "progress_revealer"
        ).set_reveal_child(True)

    def on_progress(self, upd_type, progress, description=None):
        with self.lock:
            if progress > 1.0:
                LOGGER.warning(
                    "Invalid progression (%f) for [%s]",
                    progress, upd_type
                )
                progress = 1.0

            self.progresses[upd_type] = (progress, description)

            if self.thread is None:
                self.thread = threading.Thread(target=self._thread)
                self.thread.daemon = True
                self.thread.start()

    def _on_icon_draw(self, drawing_area, cairo_ctx):
        if len(self.progress_widget_trees) <= 0:
            ratio = 1.0
        else:
            ratio = sum([
                widget_tree.get_object("progress_bar").get_fraction()
                for widget_tree in self.progress_widget_trees.values()
            ]) / len(self.progress_widget_trees)

        # Translated in Python from Nautilus source code
        # (2020/02/29: src/nautilus-toolbar.c:on_operations_icon_draw())
        style_context = drawing_area.get_style_context()
        foreground = style_context.get_color(drawing_area.get_state_flags())
        background = foreground
        background.alpha *= 0.3

        w = drawing_area.get_allocated_width()
        h = drawing_area.get_allocated_height()

        Gdk.cairo_set_source_rgba(cairo_ctx, background)
        cairo_ctx.arc(w / 2.0, h / 2.0, min(w, h) / 2.0, 0, 2 * math.pi)
        cairo_ctx.fill()

        cairo_ctx.move_to(w / 2.0, h / 2.0)
        Gdk.cairo_set_source_rgba(cairo_ctx, foreground)
        cairo_ctx.arc(
            w / 2.0, h / 2.0, min(w, h) / 2.0, -math.pi / 2.0,
            (ratio * 2 * math.pi) - (math.pi / 2.0)
        )
        cairo_ctx.fill()


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'gtk_progress_widget',
            'progress_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.widgets = []
        self.core.call_success(
            "gtk_load_css",
            "openpaperwork_gtk.widgets.progress", "progress.css"
        )

    def chkdeps(self, out: dict):
        if not GDK_AVAILABLE:
            out['gdk'].update(openpaperwork_core.deps.GDK)

    def gtk_progress_make_widget(self):
        widget = ProgressWidget(self.core)
        if widget.widget is not None:
            # gtk may not be available
            self.widgets.append(widget)
        return widget.widget

    def on_progress(self, upd_type, progress, description=None):
        for widget in self.widgets:
            widget.on_progress(upd_type, progress, description)
