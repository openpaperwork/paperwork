import logging

import PIL

from openpaperwork_core.interfaces.progress import ProgressListener
from openpaperwork_core.interfaces.work_queue import WorkQueue
import openpaperwork_core
import openpaperwork_core.promise

from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.model.thumbnail import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    DocThumbnail,
    PillowUtil
)

from openpaperwork_gtk.interfaces.pixbuf import PixbufPillow

from paperwork_gtk import _
from paperwork_gtk.interfaces.doc_list import DocList, DocListListener


LOGGER = logging.getLogger(__name__)
DELAY = 0.01

# placeholders size must include borders
PLACEHOLDER_HEIGHT = THUMBNAIL_HEIGHT + 2
PLACEHOLDER_WIDTH = THUMBNAIL_WIDTH + 2


class ThumbnailTask:
    def __init__(self, plugin, doc_id, gtk_image):
        self.plugin = plugin
        self.core = plugin.core

        self.doc_id = doc_id
        self.gtk_image = gtk_image

    def set_thumbnail(self, img=None):
        if img is None:
            LOGGER.warning(
                "Failed to get thumbnail for document %s", self.doc_id
            )
            return
        pixbuf = self.core.call_success(PixbufPillow.pillow_to_pixbuf, img)
        self.gtk_image.set_from_pixbuf(pixbuf)

    def get_promise(self):
        doc_url = self.core.call_success(DocStorage.doc_id_to_url, self.doc_id)
        if doc_url is None:
            return openpaperwork_core.promise.Promise(self.core)

        def on_error(exc):
            # catch any error, otherwise if a document is corrupted,
            # the user will get far too many error messages during
            # thumbnailing
            LOGGER.error(
                "Failed to generate thumbnail of document %s",
                self.doc_id, exc_info=exc
            )

        promise = openpaperwork_core.promise.Promise(
            self.core,
            LOGGER.info, args=("Thumbnailing of document %s", self.doc_id,)
        )
        promise = promise.then(lambda *args: None)  # drop logger return value
        promise = promise.then(
            self.core.call_success(DocThumbnail.thumbnail_get_doc_promise, doc_url)
        )
        promise = promise.then(self.set_thumbnail)
        promise = promise.catch(on_error)
        return promise


class Plugin(
    openpaperwork_core.PluginBase,
    DocListListener,
):
    PRIORITY = 100

    @classmethod
    def get_deps(cls):
        return openpaperwork_core.promise.get_deps() + [
            openpaperwork_core.Dependency(
                interface=DocStorage,
                defaults=['paperwork_backend.model.workdir'],
            ),
            openpaperwork_core.Dependency(
                interface=DocList,
                defaults=['paperwork_gtk.maindow.doclist'],
            ),
            openpaperwork_core.Dependency(
                interface=PillowUtil,
                defaults=['openpaperwork_core.pillow.util'],
            ),
            openpaperwork_core.Dependency(
                interface=PixbufPillow,
                defaults=['openpaperwork_gtk.pixbuf.pillow'],
            ),
            openpaperwork_core.Dependency(
                interface=ProgressListener,
                defaults=[],
                optional=True,
            ),
            openpaperwork_core.Dependency(
                interface=DocThumbnail,
                defaults=['paperwork_backend.model.thumbnail'],
            ),
            openpaperwork_core.Dependency(
                interface=WorkQueue,
                defaults=['openpaperwork_core.work_queue.default'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)

        self.running = False

        self.nb_loaded = 0
        self.nb_to_load = 0
        self._progress_str = None

        self.processing_docs = set()
        self.processed_docs = set()

        img = PIL.Image.new(
            "RGB",
            (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT),
            color="#EEEEEE"
        )
        self.default_thumbnail = self.core.call_success(
            PixbufPillow.pillow_to_pixbuf, img
        )
        self.core.call_all(
            WorkQueue.work_queue_create, "thumbnailer", stop_on_quit=True
        )
        self._progress_str = _("Loading document thumbnails")

    def on_doclist_initialized(self):
        self.core.call_all(WorkQueue.work_queue_cancel_all, "thumbnailer")

    def on_doc_list_clear(self):
        self.processed_docs = set()
        self.on_doc_list_visibility_changed()

    def on_doc_list_visibility_changed(self):
        self.core.call_all(WorkQueue.work_queue_cancel_all, "thumbnailer")
        self.processing_docs = set()
        self.nb_to_load = 0

    def on_doc_box_creation(self, doc_id, gtk_row, gtk_custom_flowlayout):
        gtk_img = gtk_row.thumbnail
        gtk_img.set_size_request(PLACEHOLDER_WIDTH, PLACEHOLDER_HEIGHT)
        gtk_img.set_visible(True)

    def on_doc_box_visible(self, doc_id, gtk_row, gtk_custom_flowlayout):
        if doc_id in self.processing_docs:
            return
        if doc_id in self.processed_docs:
            return

        self.nb_to_load += 1
        self.processing_docs.add(doc_id)

        task = ThumbnailTask(self, doc_id, gtk_row.thumbnail)
        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        promise = openpaperwork_core.promise.DelayPromise(
            self.core, DELAY
        )
        promise = promise.then(task.get_promise())

        def _when_loaded():
            self.nb_loaded += 1
            if doc_id in self.processing_docs:
                self.processing_docs.remove(doc_id)
                self.processed_docs.add(doc_id)
            self._update_progress()

        promise = promise.then(_when_loaded)

        self.core.call_success(
            WorkQueue.work_queue_add_promise, "thumbnailer", promise
        )

    def _update_progress(self):
        if self.nb_loaded > self.nb_to_load:
            self.nb_loaded = 0
            self.nb_to_load = 0
            self.core.call_all(ProgressListener.on_progress, "thumbnailing", 1.0)
            return

        self.core.call_all(
            ProgressListener.on_progress, "thumbnailing", self.nb_loaded / self.nb_to_load,
            self._progress_str
        )
