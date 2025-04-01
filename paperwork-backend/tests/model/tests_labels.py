import unittest

import openpaperwork_core


class TestLabels(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.model.labels")
        self.core.init()

        self.config = self.core.get_by_name("openpaperwork_core.config.fake")
        self.config.settings = {
            "workdir": "file:///some_work_dir"
        }

        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_label_color_from_rgb(self):
        self.assertEqual(
            self.core.call_success(
                "label_color_from_rgb",
                (0.9607843137254902, 0.4745098039215686, 0.0)
            ),
            "#f50079000000"
        )

    def test_has_labels(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                },
            },
        }

        self.assertTrue(
            self.core.call_success(
                "doc_has_labels_by_url", "file:///some_work_dir/some_doc"
            ) is None
        )

        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                    "labels": (
                        "label A,#aaaabbbbcccc\n"
                        "label B,#ccccbbbbaaaa\n"
                    )
                },
            },
        }

        self.assertTrue(
            self.core.call_success(
                "doc_has_labels_by_url", "file:///some_work_dir/some_doc"
            ) is not None
        )

    def test_doc_get_labels(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                    "labels": (
                        "label A,#aaaabbbbcccc\n"
                        "label B,#ccccbbbbaaaa\n"
                    )
                },
            },
        }

        labels = set()
        self.core.call_success(
            "doc_get_labels_by_url", labels, "file:///some_work_dir/some_doc"
        )
        labels = list(labels)
        labels.sort()

        self.assertEqual(
            labels,
            [
                ("label A", "#aaaabbbbcccc"),
                ("label B", "#ccccbbbbaaaa"),
            ]
        )

    def test_load_all_labels(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                    "labels": (
                        "label A,#aaaabbbbcccc\n"
                        "label B,#ccccbbbbaaaa\n"
                    )
                },
                "some_other_doc": {
                    "labels": (
                        "label B,#ccccbbbbaaaa\n"
                        "label C,#000011112222\n"
                    )
                },
            },
        }

        core = self.core

        class FakeModule(object):
            __name__ = "mainloop_stopper"

            class Plugin(openpaperwork_core.PluginBase):
                def is_doc(self, doc_url):
                    return True

                def on_label_loading_end(self):
                    core.call_all("mainloop_quit_graceful")

        self.core._load_module("mainloop_stopper", FakeModule())
        self.core.init()

        promises = []
        self.core.call_all('sync', promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        promise.schedule()

        self.core.call_one("mainloop")

        labels = set()
        self.core.call_all("labels_get_all", labels)
        labels = list(labels)
        labels.sort()

        self.assertEqual(
            labels,
            [
                ("label A", "#aaaabbbbcccc"),
                ("label B", "#ccccbbbbaaaa"),
                ("label C", "#000011112222"),
            ]
        )

    def test_doc_add_labels(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                    "labels": (
                        "label A,#aaaabbbbcccc\n"
                        "label B,#ccccbbbbaaaa\n"
                    )
                },
            },
        }

        self.core.call_success(
            "doc_add_label_by_url", "file:///some_work_dir/some_doc",
            label="label C", color="#123412341234"
        )

        labels = set()
        self.core.call_success(
            "doc_get_labels_by_url", labels, "file:///some_work_dir/some_doc"
        )
        labels = list(labels)
        labels.sort()

        self.assertEqual(
            labels,
            [
                ("label A", "#aaaabbbbcccc"),
                ("label B", "#ccccbbbbaaaa"),
                ("label C", "#123412341234"),
            ]
        )

    def test_doc_remove_labels(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                    "labels": (
                        "label A,#aaaabbbbcccc\n"
                        "label B,#ccccbbbbaaaa\n"
                    )
                },
            },
        }

        self.core.call_success(
            "doc_remove_label_by_url", "file:///some_work_dir/some_doc",
            label="label A"
        )

        labels = set()
        self.core.call_success(
            "doc_get_labels_by_url", labels, "file:///some_work_dir/some_doc"
        )
        labels = list(labels)
        labels.sort()

        self.assertEqual(
            labels,
            [
                ("label B", "#ccccbbbbaaaa"),
            ]
        )
