import logging

import PIL
import PIL.Image

from .. import (
    PluginBase,
    promise
)


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    FILE_EXTENSIONS = [
        "bmp",
        "gif",
        "jpeg",
        "jpg",
        "png",
        "tif",
        "tiff",
    ]

    @classmethod
    def get_interfaces(cls):
        return [
            'page_img_size',
            'pillow',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python']
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': 'pillow_util',
                'defaults': ['openpaperwork_core.pillow.util'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def _check_is_img(self, file_url):
        return file_url.rsplit(".", 1)[-1].lower() in self.FILE_EXTENSIONS

    def url_to_img_size(self, file_url):
        if not self._check_is_img(file_url):
            return None

        task = "url_to_img_size({})".format(file_url)
        size = (0, 0)
        self.core.call_all("on_perfcheck_start", task)
        try:
            with self.core.call_success("fs_open", file_url, mode='rb') as fd:
                img = PIL.Image.open(fd)
                size = img.size
            return size
        except PIL.Image.DecompressionBombError as exc:
            LOGGER.warning("Image %s is too big", file_url, exc_info=exc)
            return self.core.call_success(
                "pillow_get_error", "too_big"
            ).size
        finally:
            self.core.call_all("on_perfcheck_stop", task, size=size)

    def url_to_img_size_promise(self, file_url):
        if not self._check_is_img(file_url):
            return None

        return promise.ThreadedPromise(
            self.core, self.url_to_img_size, args=(file_url,)
        )

    def url_to_pillow(self, file_url):
        if not self._check_is_img(file_url):
            return None

        task = "url_to_pillow({})".format(file_url)
        size = (0, 0)
        self.core.call_all("on_perfcheck_start", task)
        try:
            with self.core.call_success("fs_open", file_url, mode='rb') as fd:
                img = PIL.Image.open(fd)
                img.load()
                self.core.call_all("on_objref_track", img)
                size = img.size
            return img
        except PIL.Image.DecompressionBombError as exc:
            LOGGER.warning("Image %s is too big", file_url, exc_info=exc)
            return self.core.call_success(
                "pillow_get_error", "too_big"
            )
        except Exception as exc:
            LOGGER.warning("Image %s corrupted", file_url, exc_info=exc)
            return self.core.call_success(
                "pillow_get_error", "invalid"
            )
        finally:
            self.core.call_all("on_perfcheck_stop", task, size=size)

    def url_to_pillow_promise(self, file_url):
        return promise.ThreadedPromise(
            self.core, self.url_to_pillow, args=(file_url,)
        )

    def pillow_to_url(self, img, file_url, format=None, quality=0.75):
        expected_format = file_url.rsplit(".", 1)[-1].upper()
        if expected_format == "JPG":
            expected_format = "JPEG"
        if expected_format == "TIF":
            expected_format = "TIFF"
        if format is None:
            format = expected_format
        if format != expected_format:
            LOGGER.warning(
                "File %s written with format %s. Expected %s",
                file_url, format, expected_format
            )
        if format != 'PNG':
            # drop the alpha channel if there is one
            img = img.convert("RGB")
        with self.core.call_success("fs_open", file_url, mode='wb') as fd:
            return img.save(
                fd, format=format, optimize=True, quality=int(quality * 100)
            )
