import logging

import openpaperwork_core

from openpaperwork_gtk.interfaces.gesture import AutoscrollingGesture

from paperwork_gtk.interfaces.doc_viewer import DocViewerControllerFactory
from paperwork_gtk.mainwindow.docview.controllers import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class AutoScrollingController(BaseDocViewController):
    def __init__(self, core, plugin):
        super().__init__(core, plugin)
        self.handler = None
        self.enter()

    def enter(self):
        if self.handler is not None:
            return
        self.handler = self.core.call_success(
            AutoscrollingGesture.gesture_enable_autoscrolling, self.plugin.scroll
        )

    def exit(self):
        if self.handler is None:
            return
        self.handler.disable()
        self.handler = None

    def on_close(self):
        self.exit()


class Plugin(
    openpaperwork_core.PluginBase,
    DocViewerControllerFactory,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=AutoscrollingGesture,
                defaults=['openpaperwork_gtk.gesture.autoscrolling'],
            ),
        ]

    def gtk_docview_get_controllers(self, out: dict, docview):
        out['autoscrolling'] = AutoScrollingController(self.core, docview)
