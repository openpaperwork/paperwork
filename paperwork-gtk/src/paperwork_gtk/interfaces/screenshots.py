import abc


class AppMenuScreenshoter(abc.ABC):
    @abc.abstractmethod
    def gtk_open_app_menu(self):
        ...

    @abc.abstractmethod
    def screenshot_snap_app_menu(self, out_file):
        ...
