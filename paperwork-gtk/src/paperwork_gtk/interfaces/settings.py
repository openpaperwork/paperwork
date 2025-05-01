import abc


class GtkSettingsOcr(abc.ABC):
    @abc.abstractmethod
    def complete_ocr_settings(self, parent_widget_tree):
        ...


class GtkSettingsScanCalibration(abc.ABC):
    @abc.abstractmethod
    def display_calibration_screen(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def hide_calibration_screen(self, *args, **kwargs):
        ...


class GtkSettingsScannerSetting(abc.ABC):
    @abc.abstractmethod
    def complete_scanner_settings(
            self, global_widget_tree, parent_widget_tree,
            list_scanner_promise):
        ...


class GtkSettingsScannerExtra(abc.ABC):
    @abc.abstractmethod
    def settings_scanner_get_extra_widget(self):
        ...
