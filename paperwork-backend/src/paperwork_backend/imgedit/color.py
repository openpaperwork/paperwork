import pillowfight

import openpaperwork_core

from . import AbstractImgEditor


class ColorImgEditor(AbstractImgEditor):
    def transform(self, img, preview=False):
        return pillowfight.ace(
            img, samples=50 if preview else 200
        )


class Plugin(openpaperwork_core.PluginBase):
    NAME = 'color_equalization'

    @classmethod
    def get_interfaces(cls):
        return ['img_editor']

    def img_editor_get_names(self, out: list):
        out.append(self.NAME)

    def img_editor_get(self, name, *args, **kwargs):
        if name != self.NAME:
            return None
        return ColorImgEditor()

    def img_editor_set(self, inout: list, name, *args, **kwargs):
        if name != self.NAME:
            return None
        c = ColorImgEditor()
        if c in inout:
            # an ACE editor is already in the list
            return
        inout.append(c)

    def img_editor_unset(self, inout: list, name):
        if name != self.NAME:
            return None
        c = ColorImgEditor()
        while c in inout:
            inout.remove(c)
