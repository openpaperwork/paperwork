"""
Plugin providing a controller object for page editing. This controller object
uses a paperwork_backend.imgedit.AbstractPageEditorUI object to tells the UI
what to do. The UI must reciprocate by transmitting some events to the
controller object.
"""

import logging

import openpaperwork_core
import openpaperwork_core.promise

from .. import _


LOGGER = logging.getLogger(__name__)


class Frame(object):
    def __init__(self, editor, original):
        # convert the frame coordinates into a more convenient format
        self.editor = editor
        self.original = original

    def get(self):
        frame = None
        for (e, img_size) in zip(
                    self.editor.active_modifiers, self.editor.img_sizes
                ):
            if hasattr(e, 'frame'):
                frame = e.frame
            elif frame is not None:
                frame = e.transform_frame(img_size, frame)
        return frame

    def set(self, frame):
        for (e, img_size) in zip(
                    reversed(self.editor.active_modifiers),
                    reversed(self.editor.img_sizes)
                ):
            if hasattr(e, 'frame'):
                e.frame = frame
            else:
                frame = e.untransform_frame(img_size, frame)


class PageEditor(object):
    def __init__(self, core, doc_url, page_idx, page_editor_ui):
        self.core = core
        self.ui = page_editor_ui
        self.doc_url = doc_url
        self.page_idx = page_idx

        if doc_url is not None:
            page_url = self.core.call_success(
                "page_get_img_url", doc_url, page_idx, write=False
            )
            self.original_img = self.core.call_success(
                "url_to_pillow", page_url
            )

            # The frame coordinates we keep here are relative to the original
            # image (not the resulting image, that can, for instance, be
            # rotated)
            # TODO(Jflesch): We should use libpillowfight.scan_border()
            # to predefined an useful frame.
            original_frame = ((0, 0), self.original_img.size)
        else:
            self.original_img = None
            original_frame = ((0, 0), (0, 0))

        self.frame = Frame(self, original_frame)
        modifiers = []
        self.core.call_all("img_editor_get_names", modifiers)

        self.modifier_descriptors = {}
        if 'color_equalization' in modifiers:
            self.modifier_descriptors['color_equalization'] = {
                "id": "color_equalization",
                "name": _("Color equalization"),
                "modifier": 'color_equalization',
                "default_kwargs": {},
                "need_frame": False,
                "togglable": True,
                "enabled": False,
                "priority": -999,
            }
        if ('cropping' in modifiers
                and self.ui.can(self.ui.CAPABILITY_SHOW_FRAME)):
            self.modifier_descriptors['crop'] = {
                "id": "crop",
                "name": _("Cropping"),
                "modifier": 'cropping',
                "default_kwargs": {},
                "need_frame": True,
                "togglable": True,
                "enabled": False,
                "priority": 100,
            }
        if 'rotation' in modifiers:
            self.modifier_descriptors['rotate_clockwise'] = {
                "id": "rotate_clockwise",
                "name": _("Clockwise Rotation"),
                "modifier": 'rotation',
                "default_kwargs": {'angle': 90},
                "need_frame": False,
                "togglable": False,
                "priority": 50,
            }
            self.modifier_descriptors['rotate_counterclockwise'] = {
                "id": "rotate_counterclockwise",
                "name": _("Counterclockwise Rotation"),
                "modifier": 'rotation',
                "default_kwargs": {'angle': -90},
                "need_frame": False,
                "togglable": False,
                "priority": 49,
            }
        self.active_modifiers = []
        # image sizes before transformation of each modifier
        self.img_sizes = []

        if self.ui is not None:
            self._refresh_preview()
            self._refresh_frame()

    def get_modifiers(self):
        r = list(self.modifier_descriptors.values())
        r.sort(key=lambda m: -m['priority'])
        return r

    def _needs_frame(self):
        if not self.ui.can(self.ui.CAPABILITY_SHOW_FRAME):
            return
        for e in self.active_modifiers:
            if hasattr(e, 'frame'):
                return True
        return False

    def _refresh_modifiers(self):
        for modifier in self.modifier_descriptors.values():
            enabled = False
            if modifier['togglable'] and modifier['enabled']:
                enabled = True
            self.ui.set_modifier_state(modifier['id'], enabled)

    def _refresh_preview(self):
        img = self.original_img
        self.img_sizes = []
        for e in self.active_modifiers:
            self.img_sizes.append(img.size)
            img = e.transform(img, preview=True)
        self.core.call_one("mainloop_execute", self.ui.show_preview, img)

    def _refresh_frame(self):
        if not self._needs_frame():
            self.core.call_one("mainloop_execute", self.ui.hide_frame_selector)
            return
        self.core.call_one(
            "mainloop_execute", self.ui.show_frame_selector
        )

    def _on_modifier_selected(self, modifier_id):
        modifier_descriptor = self.modifier_descriptors[modifier_id]

        if modifier_descriptor['togglable'] and modifier_descriptor['enabled']:
            self.core.call_all(
                "img_editor_unset",
                self.active_modifiers,
                modifier_descriptor['modifier']
            )
            modifier_descriptor['enabled'] = False
        else:
            self.core.call_all(
                "img_editor_set",
                self.active_modifiers,
                modifier_descriptor['modifier'],
                **modifier_descriptor['default_kwargs']
            )
            modifier_descriptor['enabled'] = True

        self._refresh_modifiers()
        self._refresh_preview()
        self._refresh_frame()

    def on_modifier_selected(self, modifier_id):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self._on_modifier_selected, args=(modifier_id,)
        )

    def _on_save(self):
        img = self.original_img
        for e in self.active_modifiers:
            img = e.transform(img, preview=False)
        page_url = self.core.call_success(
            "page_get_img_url", self.doc_url, self.page_idx, write=True
        )
        self.core.call_success("pillow_to_url", img, page_url)
        # Drop the text so the OCR will be run again
        self.core.call_success(
            "page_set_boxes_by_url", self.doc_url, self.page_idx, []
        )
        self.core.call_success(
            "mainloop_schedule", self.ui.on_edit_end,
            self.doc_url, self.page_idx
        )

    def on_save(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self._on_save
        )

    def on_cancel(self):
        self.active_modifiers = []
        self.ui.on_edit_end(self.doc_url, self.page_idx)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['page_editor']

    def get_deps(self):
        return [
            {
                "interface": "img_editor",
                'defaults': [
                    'paperwork_backend.imgedit.color',
                    'paperwork_backend.imgedit.crop',
                    'paperwork_backend.imgedit.rotate',
                ],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'openpaperwork_core.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ]
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def page_editor_get(self, doc_url, page_idx, page_editor_ui):
        return PageEditor(self.core, doc_url, page_idx, page_editor_ui)
