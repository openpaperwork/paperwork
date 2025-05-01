import os
import unittest

import PIL.Image

import openpaperwork_core

from paperwork_backend.interfaces.img_editor import ImgEditorFactory


class TestImgEdit(unittest.TestCase):
    def setUp(self):
        self.test_img = PIL.Image.open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_img.png"
            )
        )

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.imgedit.color")
        self.core.load("paperwork_backend.imgedit.crop")
        self.core.load("paperwork_backend.imgedit.rotate")
        self.core.init()

    def test_get_names(self):
        out = []
        self.core.call_success(ImgEditorFactory.img_editor_get_names, out)
        out.sort()
        self.assertEqual(out, ['color_equalization', 'cropping', 'rotation'])

    def test_all(self):
        editors = [
            self.core.call_success(ImgEditorFactory.img_editor_get, "rotation", angle=90),
            self.core.call_success(ImgEditorFactory.img_editor_get, "color_equalization"),
        ]

        # the input image is 200x100
        frame = (50, 25, 150, 75)
        for e in editors:
            frame = e.transform_frame(self.test_img.size, frame)
        editors.append(
            self.core.call_success(ImgEditorFactory.img_editor_get, "cropping", frame=frame)
        )

        img = self.test_img
        for e in editors:
            img = e.transform(img)

        self.assertEqual(img.size, (50, 100))
