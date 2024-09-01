import logging
import random

import openpaperwork_core
import openpaperwork_core.promise

from .. import _

LOGGER = logging.getLogger(__name__)

LABELS_FILENAME = "labels"


COLOR_NAMES = [
    ('aqua', (0, 1, 1)),
    ('black', (0, 0, 0)),
    ('blue', (0, 0, 1)),
    ('fuchsia', (1, 0, 1)),
    ('gray', (0x80 / 0xFF, 0x80 / 0xFF, 0x80 / 0xFF)),
    ('green', (0, 0x80 / 0xFF, 0)),
    ('lime', (0, 1, 0)),
    ('maroon', (0x80 / 0xFF, 0, 0)),
    ('navy', (0, 0, 0x80 / 0xFF)),
    ('olive', (0x80 / 0xFF, 0x80 / 0xFF, 0)),
    ('purple', (0x80 / 0xFF, 0, 0x80 / 0xFF)),
    ('red', (1, 0, 0)),
    ('silver', (0xC0 / 0xFF, 0xC0 / 0xFF, 0xC0 / 0xFF)),
    ('teal', (0, 0x80 / 0xFF, 0x80 / 0xFF)),
    ('white', (1, 1, 1)),
    ('yellow', (1, 1, 0)),
]


class LabelLoader(object):
    """
    Go through all the documents to figure out what labels exist.
    """
    def __init__(self, plugin):
        self.plugin = plugin
        self.core = plugin.core
        self.all_docs = []

    def get_promise(self):
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=("storage_get_all_docs", self.all_docs)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_all, "on_label_loading_start",
        )
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, self.load_labels
            )
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_all, "on_label_loading_end"
        )

        return promise

    def load_labels(self, *args, **kwargs):
        nb_docs = len(self.all_docs)

        LOGGER.info("Loading labels from %d documents", nb_docs)
        for (doc_idx, (doc_id, doc_url)) in enumerate(self.all_docs):
            self.core.call_all(
                "on_progress", "label_loading",
                doc_idx / nb_docs,
                _("Loading labels of document {}").format(doc_id)
            )
            labels = set()
            self.plugin.doc_get_labels_by_url(labels, doc_url)
            for label in labels:
                self.plugin.all_labels[label[0]] = label[1]
        self.core.call_all("on_progress", "label_loading", 1.0)
        LOGGER.info(
            "%d labels loaded from %d documents",
            len(self.plugin.all_labels), nb_docs
        )


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 20000

    def __init__(self):
        # {label_name: color, label_name: color, ...}
        self.all_labels = {}

    def get_interfaces(self):
        return [
            "doc_labels",
            "syncable",
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def doc_internal_get_mtime_by_url(self, out: list, doc_url):
        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        if self.core.call_success("fs_exists", labels_url) is None:
            return
        out.append(self.core.call_success("fs_get_mtime", labels_url))

    def doc_has_labels_by_url(self, doc_url):
        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        return self.core.call_success("fs_exists", labels_url)

    def doc_get_labels_by_url(self, out: set, doc_url):
        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        if self.core.call_success("fs_exists", labels_url) is None:
            return
        with self.core.call_success("fs_open", labels_url, 'r') as file_desc:
            for line in file_desc.readlines():
                line = line.strip()
                if line == "":
                    continue
                # Expected: ('label', '#rrrrggggbbbb')
                out.add(tuple(x.strip() for x in line.split(",", 1)))

    def doc_get_labels_by_url_promise(self, out: list, doc_url):
        def get_labels(labels=None):
            if labels is None:
                labels = set()
            self.doc_get_labels_by_url(labels, doc_url)
            return labels

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, get_labels
        )
        out.append(promise)

    def label_generate_color(self):
        color = (
            random.randint(0, 255) / 255,
            random.randint(0, 255) / 255,
            random.randint(0, 255) / 255,
        )
        return self.label_color_from_rgb(color)

    def label_get_foreground_color(self, bg_color):
        brightness = (
            (bg_color[0] * 0.299)
            + (bg_color[1] * 0.587)
            + (bg_color[2] * 0.114)
        )
        if brightness > (69 / 255):
            return (0, 0, 0)  # black
        else:
            return (1, 1, 1)  # white

    def doc_add_label_by_url(self, doc_url, label, color=None):
        assert "," not in label
        current = set()
        self.doc_get_labels_by_url(current, doc_url)
        current = {k: v for (k, v) in current}
        if label in current:
            LOGGER.warning(
                "Label '%s' already on document '%s'", label, doc_url
            )
            return

        if color is not None:
            self.all_labels[label] = color
        if label in self.all_labels:
            color = self.all_labels[label]
        else:
            color = self.label_generate_color()

        LOGGER.info("Adding label '%s' on document '%s'", label, doc_url)

        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        with self.core.call_success("fs_open", labels_url, 'a') as file_desc:
            file_desc.write("{},{}\n".format(label, color))

        if label not in self.all_labels:
            self.all_labels[label] = color

        return True

    def doc_remove_label_by_url(self, doc_url, label):
        LOGGER.info("Removing label '%s' from document '%s'", label, doc_url)

        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        if self.core.call_success("fs_exists", labels_url) is None:
            return

        with self.core.call_success("fs_open", labels_url, 'r') as file_desc:
            labels = file_desc.readlines()

        labels = [lab.strip() for lab in labels]
        labels = [lab.split(",", 1) for lab in labels if len(lab) > 0]
        labels = {l: c for (l, c) in labels}
        try:
            labels.pop(label)
        except KeyError:
            LOGGER.warning(
                "Tried to remove label '%s' from document '%s', but label"
                " was not found on the document", label, doc_url
            )

        labels = [(label, color) for (label, color) in labels.items()]
        labels.sort()

        with self.core.call_success("fs_open", labels_url, "w") as file_desc:
            for (label, color) in labels:
                file_desc.write("{},{}\n".format(label, color))
        return True

    def labels_get_all(self, out: set):
        for (label, color) in self.all_labels.items():
            out.add((label, color))

    def label_color_to_rgb(self, color):
        if color[0] == '#':
            if len(color) == 13:
                return (
                    int(color[1:5], 16) / 0xFFFF,
                    int(color[5:9], 16) / 0xFFFF,
                    int(color[9:13], 16) / 0xFFFF,
                )
            else:
                return (
                    int(color[1:3], 16) / 0xFF,
                    int(color[3:5], 16) / 0xFF,
                    int(color[5:7], 16) / 0xFF,
                )
        else:
            if color.startswith("rgb("):
                color = color[len("rgb("):-1]
            elif color.startswith("("):
                color = color[len("("):-1]
            color = color.split(",")
            color = tuple([int(x.strip()) for x in color])
            color = (color[0] / 0xFF, color[1] / 0xFF, color[2] / 0xFF)
            return color

    def label_color_from_rgb(self, color):
        return (
            "#"
            + format(int(color[0] * 0xFF), '02x') + "00"
            + format(int(color[1] * 0xFF), '02x') + "00"
            + format(int(color[2] * 0xFF), '02x') + "00"
        )

    def label_color_rgb_to_text(self, color):
        for (name, rgb) in COLOR_NAMES:
            if color == rgb:
                break
        else:
            def color_distance(a, b):
                return (
                    (abs(a[0] - b[0]) ** 2) +
                    (abs(a[1] - b[1]) ** 2) +
                    (abs(a[2] - b[2]) ** 2)
                )

            closest_color = min((
                (color_distance(rgb, color), name)
                for (name, rgb) in COLOR_NAMES
            ))
            name = "~" + closest_color[1]

        return "#{:02X}{:02X}{:02X} ({})".format(
            int(color[0] * 0xFF),
            int(color[1] * 0xFF),
            int(color[2] * 0xFF),
            name
        )

    def label_load_all(self, promises: list):
        self.all_labels = {}
        promise = LabelLoader(self).get_promise()
        # drop the return value of 'call_all'
        promise = promise.then(lambda *args, **kwargs: None)
        promises.append(promise)

    def sync(self, promises: list):
        self.label_load_all(promises)
