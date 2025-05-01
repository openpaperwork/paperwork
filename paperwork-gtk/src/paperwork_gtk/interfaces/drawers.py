import abc


class AbstractFrameDrawer(abc.ABC):
    @abc.abstractmethod
    def stop(self):
        ...

    @abc.abstractmethod
    def request_redraw(self):
        ...


class FrameDrawerFactory(abc.ABC):
    """
    Frame the user can move around and resize
    """
    @abc.abstractmethod
    def draw_frame_start(
            self, drawing_area, content_full_size,
            get_frame_cb, set_frame_cb=None) -> AbstractFrameDrawer:
        ...

    @abc.abstractmethod
    def draw_frame_stop(self, drawing_area):
        ...


class ScanDrawerFactory(abc.ABC):
    @abc.abstractmethod
    def draw_scan_start(self, drawing_area, scan_id=None):
        ...

    @abc.abstractmethod
    def draw_scan_stop(self, drawing_area):
        ...

    @abc.abstractmethod
    def draw_scan_get_scan_size(self, scan_id):
        ...


class CalibrationDrawerFactory(abc.ABC):
    @abc.abstractmethod
    def draw_calibration_start(self, drawing_area, content_full_size, read_only=False):
        ...

    @abc.abstractmethod
    def draw_calibration_stop(self, drawing_area):
        ...
