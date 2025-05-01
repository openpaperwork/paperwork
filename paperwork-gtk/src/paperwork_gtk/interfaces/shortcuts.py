import abc


class AppShortcutHelp(abc.ABC):
    @abc.abstractmethod
    def shortcut_help_add(
        self, shortcut_group, shortcut_desc, shortcut_keys, action_name
    ):
        ...

    @abc.abstractmethod
    def gtk_show_shortcuts(self):
        ...

    @abc.abstractmethod
    def gtk_hide_shortcuts(self):
        ...


class AppShortcutCollector(abc.ABC):
    @abc.abstractmethod
    def app_shortcut_add(self, shortcut_group, shortcut_desc, shortcut_keys, action_name):
        ...
