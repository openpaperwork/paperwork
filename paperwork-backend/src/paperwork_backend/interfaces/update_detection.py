import abc


class UpdateDetectionListener(abc.ABC):
    @abc.abstractmethod
    def on_update_detected(self, local_version, remote_version):
        ...


class UpdateDetection(abc.ABC):
    @abc.abstractmethod
    def update_check(self):
        ...

    @abc.abstractmethod
    def update_compare(self):
        ...
