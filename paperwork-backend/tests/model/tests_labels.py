import unittest

from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core

from paperwork_backend.interfaces.doc_labels import DocLabelColors
from paperwork_backend.interfaces.doc_labels import DocLabelListener
from paperwork_backend.interfaces.doc_labels import DocLabels
from paperwork_backend.interfaces.docs import DocType
from paperwork_backend.interfaces.sync import Syncable


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
                DocLabelColors.label_color_from_rgb,
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
                DocLabels.doc_has_labels_by_url, "file:///some_work_dir/some_doc"
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
                DocLabels.doc_has_labels_by_url, "file:///some_work_dir/some_doc"
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
            DocLabels.doc_get_labels_by_url, labels, "file:///some_work_dir/some_doc"
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

            class Plugin(
                openpaperwork_core.PluginBase,
                DocLabelListener,
                DocType,
            ):
                def is_doc(self, doc_url):
                    return True

                def doc_internal_get_mtime_by_url(self, out: list, doc_url):
                    pass

                def doc_internal_get_nb_pages_by_url(self, out: list, doc_url):
                    pass

                def on_label_loading_start(self):
                    pass

                def on_label_loading_end(self):
                    core.call_all(Mainloop.mainloop_quit_graceful)

        self.core.load("mainloop_stopper", FakeModule())
        self.core.init()

        promises = []
        self.core.call_all(Syncable.sync, promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        promise.schedule()

        self.core.call_one(Mainloop.mainloop)

        labels = set()
        self.core.call_all(DocLabels.labels_get_all, labels)
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
            DocLabels.doc_add_label_by_url, "file:///some_work_dir/some_doc",
            label="label C", color="#123412341234"
        )

        labels = set()
        self.core.call_success(
            DocLabels.doc_get_labels_by_url, labels, "file:///some_work_dir/some_doc"
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
            DocLabels.doc_remove_label_by_url, "file:///some_work_dir/some_doc",
            label="label A"
        )

        labels = set()
        self.core.call_success(
            DocLabels.doc_get_labels_by_url, labels, "file:///some_work_dir/some_doc"
        )
        labels = list(labels)
        labels.sort()

        self.assertEqual(
            labels,
            [
                ("label B", "#ccccbbbbaaaa"),
            ]
        )
