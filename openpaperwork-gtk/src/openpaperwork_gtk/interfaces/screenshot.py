import abc


class ScreenshotListener(abc.ABC):
    @abc.abstractmethod
    def on_screenshot_before(self):
        ...

    @abc.abstractmethod
    def on_screenshot_after(self):
        ...


class Screenshot(abc.ABC):
    @abc.abstractmethod
    def screenshot_snap_all_promise(self, temporary=True, name="screenshots"):
        ...

    @abc.abstractmethod
    def screenshot_snap_widget(
        self, gtk_widget, out_file_url, margins=(20, 20, 20, 20),
        highlight=(0.67, 0.80, 0.93)
    ):
        ...


class ScreenshotProvider(abc.ABC):
    @abc.abstractmethod
    def screenshot_snap_all_doc_widgets(self, out_dir):
        ...
