import logging

import PIL
import PIL.Image
import pillowfight

import openpaperwork_core

from . import AbstractImgEditor


LOGGER = logging.getLogger(__name__)


class CropImgEditor(AbstractImgEditor):
    def __init__(self, frame=None, **kwargs):
        self.frame = frame

    def transform(self, img, preview=False):
        if self.frame is None:
            # optimize the default frame
            LOGGER.info("Guessing new default cropping frame ...")

            # It's actually faster to resize down the image than look
            # for the scan borders on the full-size image.
            smaller_img = img.resize(
                (int(img.size[0] / 2), int(img.size[1] / 2)),
                getattr(PIL.Image, 'Resampling', PIL.Image).LANCZOS
            )
            frame = pillowfight.find_scan_borders(smaller_img)

            if frame[0] >= frame[2] or frame[1] >= frame[3]:
                LOGGER.info("Failed to guess a cropping frame")
                # defaulting to the whole image
                self.frame = (0, 0, img.size[0], img.size[1])
            else:
                # if we have found a valid frame
                LOGGER.info("Guessed cropping frame: %s", frame)
                self.frame = (
                    frame[0] * 2, frame[1] * 2, frame[2] * 2, frame[3] * 2
                )

        if preview:
            # we do not crop the preview. The UI displays a frame on top
            # of it showing where the cropping will happen.
            return img

        img = img.crop(self.frame)
        return img


class Plugin(openpaperwork_core.PluginBase):
    NAME = 'cropping'

    def get_interfaces(self):
        return ['img_editor']

    def img_editor_get_names(self, out: list):
        out.append(self.NAME)

    def img_editor_get(self, name, *args, **kwargs):
        if name != self.NAME:
            return None
        return CropImgEditor(**kwargs)

    def img_editor_set(self, inout: list, name, *args, **kwargs):
        if name != self.NAME:
            return None
        c = CropImgEditor(**kwargs)
        try:
            # Check if we already have a CropImgEditor in the list.
            # If so, do nothing
            inout.index(c)
        except ValueError:
            inout.append(c)

    def img_editor_unset(self, inout: list, name):
        if name != self.NAME:
            return None
        c = CropImgEditor()
        while c in inout:
            inout.remove(c)
