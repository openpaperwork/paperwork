import logging

import openpaperwork_core

from . import BaseDocViewController


LOGGER = logging.getLogger(__name__)


class AutoScrollingController(BaseDocViewController):
    def __init__(self, plugin):
        super().__init__(plugin)
        self.handler = None
        self.enter()

    def enter(self):
        if self.handler is not None:
            return
        self.handler = self.plugin.core.call_success(
            "gesture_enable_autoscrolling", self.plugin.scroll
        )

    def exit(self):
        if self.handler is None:
            return
        self.handler.disable()
        self.handler = None

    def on_close(self):
        self.exit()


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['gtk_docview_controller']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
            {
                'interface': 'gtk_gesture_autoscrolling',
                'defaults': ['openpaperwork_gtk.gesturee.autoscrolling'],
            },
        ]

    def gtk_docview_get_controllers(self, out: dict, docview):
        out['autoscrolling'] = AutoScrollingController(docview)
