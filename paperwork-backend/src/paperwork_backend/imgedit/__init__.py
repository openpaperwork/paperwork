class AbstractImgEditor(object):
    def transform(self, img, preview=False):
        """
        Apply the transformation operation.

        Arguments:
            img -- image to transform
            preview -- indicates if we intend to use the result as a preview
                or as final result
        """
        assert False

    def transform_frame(self, img_size, frame):
        """
        From the frame applied to the original image to the resulting image.
        """
        return frame

    def untransform_frame(self, img_size, frame):
        """
        From the frame on the resulting image to the original image.
        """
        return frame

    def __eq__(self, o):
        return type(self) is type(o)
