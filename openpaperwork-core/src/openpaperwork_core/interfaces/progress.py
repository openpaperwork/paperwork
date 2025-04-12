import abc


class ProgressListener(abc.ABC):
    @abc.abstractmethod
    def on_progress(self, upd_type, progress, description=None):
        ...
