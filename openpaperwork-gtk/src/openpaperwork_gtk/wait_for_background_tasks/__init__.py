import logging
import sys
import threading
import time

from openpaperwork_core.interfaces.gui import GuiListener
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.mainloop import MainloopListener
from openpaperwork_core.interfaces.progress import ProgressListener
import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.util

from openpaperwork_gtk.interfaces.gtk import GtkResources


# TODO(Jflesch): refactor with openpaperwork_gtk.widgets.progress


LOGGER = logging.getLogger(__name__)

TIME_BETWEEN_UPDATES = 0.3
# Tasks are often chained one after the other. We don't want the button/popover
# to disappear and reappear continually. So when a task ends, we
# give them some extra time to live.
# STAY_ALIVES is the number of updates we wait before hiding them.
STAY_ALIVES = int(2.0 / TIME_BETWEEN_UPDATES)


class ProgressDialog:
    def __init__(self, plugin):
        LOGGER.info("Opening dialog 'wait for background tasks'")

        self.plugin = plugin
        self.core = plugin.core

        self.progress_widget_trees = {}

        self.dialog_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "openpaperwork_gtk.wait_for_background_tasks",
            "wait_for_background_tasks.glade"
        )
        if self.dialog_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.dialog_tree.get_object("dialog").connect(
            "response", self._suicide
        )
        self.dialog_tree.get_object("dialog").show_all()

        # A thread updates the widgets every 300ms. We don't update them
        # each time on_progress() is called to not degrade performances
        self.thread = threading.Thread(target=self._thread)
        self.thread.daemon = True
        self.thread.start()

    def _thread(self):
        self.stay_alives = STAY_ALIVES
        while self.thread is not None:
            time.sleep(TIME_BETWEEN_UPDATES)
            self.core.call_one(
                Mainloop.mainloop_execute, self._upd_progress_widgets
            )

    def _upd_progress_widgets(self):
        with self.plugin.lock:
            progresses = self.plugin.progresses.items()
            self.plugin.progresses = {}
            for (upd_type, (progress, description)) in progresses:
                self._upd_progress_widget(
                    upd_type, progress, description
                )

            if len(self.progress_widget_trees) > 0:
                self.stay_alives = STAY_ALIVES
                return

            if self.stay_alives > 0:
                self.stay_alives -= 1
                return

            self.thread = None
            self.dialog_tree.get_object("dialog").destroy()

    def _upd_progress_widget(self, upd_type, progress, description):
        box = self.dialog_tree.get_object("task_list")

        if progress >= 1.0:  # deletion of progress
            if upd_type not in self.progress_widget_trees:
                return

            LOGGER.info("Task '%s' has ended", upd_type)
            widget_tree = self.progress_widget_trees.pop(upd_type)
            details = widget_tree.get_object("progress_bar")
            box.remove(details)
            details.unparent()

            LOGGER.info(
                "Task '%s' has ended (%d remaining)",
                upd_type, len(self.progress_widget_trees)
            )
            return

        if upd_type not in self.progress_widget_trees:
            # creation of progress widget
            LOGGER.info(
                "Task '%s' has started (%d already active)",
                upd_type, len(self.progress_widget_trees)
            )
            # reuse the progress widgets from
            # openpaperwork_gtk.widgets.progress
            widget_tree = self.core.call_success(
                GtkResources.gtk_load_widget_tree,
                "openpaperwork_gtk.widgets.progress",
                "progress_details.glade"
            )
            box.add(widget_tree.get_object("progress_bar"))
            self.progress_widget_trees[upd_type] = widget_tree

        else:
            widget_tree = self.progress_widget_trees[upd_type]

        # update of progress
        progress_bar = widget_tree.get_object("progress_bar")
        progress_bar.set_fraction(progress)
        progress_bar.set_text(description if description is not None else "")

    def _suicide(self, *args, **kwargs):
        LOGGER.warning("User requested a forced quit")
        # In theory, the following shouldn't hurt any more than a power outtage
        # and is really reliable way to end Paperwork
        sys.exit(0)


class Plugin(
    openpaperwork_core.PluginBase,
    GuiListener,
    MainloopListener,
    ProgressListener,
    metaclass=openpaperwork_core.util.Singleton
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': Mainloop,
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.dialog = None
        self.progresses = {}
        self.lock = threading.Lock()
        self.nb_main_windows = 0

    def on_gui_initialized(self):
        self.nb_main_windows += 1

    @openpaperwork_core.noop
    def new_mainwindow(self):
        pass

    def _mainloop_quit_graceful(self):
        self.dialog = ProgressDialog(self)

    @openpaperwork_core.noop
    def on_mainloop_start(self):
        pass

    def on_mainloop_quit_graceful_request(self):
        self.nb_main_windows -= 1
        if self.nb_main_windows <= 0:
            self.core.call_one(Mainloop.mainloop_execute, self._mainloop_quit_graceful)

    @openpaperwork_core.noop
    def on_mainloop_quit(self):
        pass

    def on_progress(self, upd_type, progress, description=None):
        with self.lock:
            if progress > 1.0:
                LOGGER.warning(
                    "Invalid progression (%f) for [%s]",
                    progress, upd_type
                )
                progress = 1.0

            self.progresses[upd_type] = (progress, description)
