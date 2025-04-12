import abc


class GtkSingleEntryDialogListener(abc.ABC):
    @abc.abstractmethod
    def on_dialog_single_entry_reply(self, origin, result: bool, value: str, *args, **kwargs):
        ...


class GtkSingleEntryDialog(abc.ABC):
    @abc.abstractmethod
    def gtk_show_dialog_single_entry(
        self, origin, title, original_value, *args, **kwargs
    ):
        ...


class GtkYesNoDialogListener(abc.ABC):
    @abc.abstractmethod
    def on_dialog_yes_no_reply(self, origin, result: bool, *args, **kwargs):
        ...


class GtkYesNoDialog(abc.ABC):
    @abc.abstractmethod
    def gtk_show_dialog_yes_no(self, origin, msg, *args, **kwargs):
        ...
