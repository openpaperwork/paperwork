import os
import unittest

import PIL
import PIL.Image

import openpaperwork_core

from paperwork_backend.pageedit import AbstractPageEditorUI


class FakeUI(AbstractPageEditorUI):
    CAPABILITIES = AbstractPageEditorUI.CAPABILITY_SHOW_FRAME

    def __init__(self, tests):
        self.tests = tests

    def show_preview(self, img):
        self.tests.ui_calls.append(('show_preview', img))

    def show_frame_selector(self):
        self.tests.ui_calls.append(('show_frame_selector',))

    def hide_frame_selector(self):
        self.tests.ui_calls.append(('hide_frame_selector',))


class TestPageEdit(unittest.TestCase):
    def setUp(self):
        self.test_img = PIL.Image.open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_img.png"
            )
        )
        self.pillowed = []
        self.ui_calls = []

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.imgedit.color")
        self.core.load("paperwork_backend.imgedit.crop")
        self.core.load("paperwork_backend.imgedit.rotate")
        self.core.load("paperwork_backend.pageedit.pageeditor")

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999

                def pillow_to_url(s, img, dst_uri):
                    self.pillowed.append(dst_uri)
                    return dst_uri

        self.core._load_module("fake_module", FakeModule())
        self.core.init()

        self.model = self.core.get_by_name("paperwork_backend.model.fake")

    def test_all(self):
        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_imgs": [
                    ("file:///paper.0.jpeg", self.test_img),
                    ("file:///paper.1.jpeg", self.test_img),
                    ("file:///paper.2.jpeg", self.test_img),
                ],
                "page_boxes": [[], [], []],
            },
        ]

        fake_ui = FakeUI(self)

        page_editor = self.core.call_success(
            "page_editor_get",
            "file:///some_work_dir/some_doc_id", 1, fake_ui
        )

        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (200, 100))
        self.assertEqual(self.ui_calls[1][0], 'hide_frame_selector')

        modifiers = page_editor.get_modifiers()
        modifiers = [e['id'] for e in modifiers]
        modifiers.sort()
        self.assertEqual(modifiers, [
            "color_equalization",
            "crop",
            "rotate_clockwise",
            "rotate_counterclockwise",
        ])

        # rotate 90°
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("rotate_clockwise").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (100, 200))
        self.assertEqual(self.ui_calls[1][0], 'hide_frame_selector')

        # ACE
        bilinear = getattr(PIL.Image, 'Resampling', PIL.Image).BILINEAR
        avg_color = self.ui_calls[0][1].resize(
            (1, 1), resample=bilinear
        ).tobytes()
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("color_equalization").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (100, 200))
        avg_color2 = self.ui_calls[0][1].resize(
            (1, 1), resample=bilinear
        ).tobytes()
        self.assertNotEqual(avg_color, avg_color2)
        self.assertEqual(self.ui_calls[1][0], 'hide_frame_selector')

        # crop
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("crop").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (100, 200))
        self.assertEqual(self.ui_calls[1][0], 'show_frame_selector')

        page_editor.frame.set((0, 190, 10, 200))
        self.assertEqual(page_editor.frame.get(), (0, 190, 10, 200))

        # rotation again (180°)
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("rotate_clockwise").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (200, 100))
        self.assertEqual(self.ui_calls[1][0], 'show_frame_selector')
        self.assertEqual(page_editor.frame.get(), (190, 90, 200, 100))

        # .. and again (270°)
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("rotate_clockwise").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (100, 200))
        self.assertEqual(self.ui_calls[1][0], 'show_frame_selector')
        self.assertEqual(page_editor.frame.get(), (90, 0, 100, 10))

        # and save !
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_save().schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(len(self.ui_calls), 0)
        self.assertEqual(self.pillowed, ["file:///paper.1.jpeg"])
