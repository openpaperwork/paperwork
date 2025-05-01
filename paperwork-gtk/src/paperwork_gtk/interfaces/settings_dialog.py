import abc


class SettingsDialogComponent(abc.ABC):
    @abc.abstractmethod
    def complete_settings(self, settings_dialog_widget_tree):
        ...

    @abc.abstractmethod
    def on_settings_closed(self, settings_dialog_widget_tree):
        ...


class SettingsDialog(abc.ABC):
    @abc.abstractmethod
    def gtk_open_settings(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def gtk_close_settings(self):
        ...

    @abc.abstractmethod
    def add_setting_to_dialog(
        self, global_widget_tree, title, widgets, extra_widget=None
    ):
        ...

    @abc.abstractmethod
    def add_setting_screen(
        self, global_widget_tree, name, widget_header, widget_body
    ):
        ...

    @abc.abstractmethod
    def show_setting_screen(self, global_widget_tree, name):
        ...

    @abc.abstractmethod
    def settings_scroll_to_top(self):
        ...

    @abc.abstractmethod
    def settings_scroll_to_bottom(self):
        ...
