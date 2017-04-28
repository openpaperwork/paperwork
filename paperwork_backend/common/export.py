def dummy_export_progress_cb(*args, **kwargs):
    pass


class Exporter(object):
    def __init__(self, obj, export_format):
        self.obj = obj
        self.export_format = str(export_format)
        self.can_change_quality = False

    def set_quality(quality_pourcent):
        raise NotImplementedError()

    def set_postprocess_func(self, postprocess_func):
        raise NotImplementedError()

    def estimate_size():
        """
        returns the size in bytes
        """
        raise NotImplementedError()

    def get_img(self):
        """
        Returns a Pillow Image
        """
        raise NotImplementedError()

    def get_mime_type(self):
        raise NotImplementedError()

    def get_file_extensions(self):
        raise NotImplementedError()

    def save(self, target_path, progress_cb=dummy_export_progress_cb):
        raise NotImplementedError()
