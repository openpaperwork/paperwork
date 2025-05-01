from typing import List
import abc


class AbstractImgEditor(abc.ABC):
    @abc.abstractmethod
    def transform(self, img, preview=False):
        """
        Apply the transformation operation.

        Arguments:
            img -- image to transform
            preview -- indicates if we intend to use the result as a preview
                or as final result
        """
        ...

    @abc.abstractmethod
    def transform_frame(self, img_size, frame):
        """
        From the frame applied to the original image to the resulting image.
        """
        ...

    @abc.abstractmethod
    def untransform_frame(self, img_size, frame):
        """
        From the frame on the resulting image to the original image.
        """
        ...

    def __eq__(self, o):
        return type(self) is type(o)


class ImgEditorFactory(abc.ABC):
    @abc.abstractmethod
    def img_editor_get_names(self, out: list):
        ...

    @abc.abstractmethod
    def img_editor_get(self, name, *args, **kwargs) -> AbstractImgEditor:
        ...

    @abc.abstractmethod
    def img_editor_set(self, inout: List[AbstractImgEditor], name, *args, **kwargs):
        ...

    @abc.abstractmethod
    def img_editor_unset(self, inout: list, name):
        ...
