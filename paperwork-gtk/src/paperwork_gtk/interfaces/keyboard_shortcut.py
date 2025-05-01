import abc


class KeyboardShortcutCollector(abc.ABC):
    @abc.abstractmethod
    def app_shortcut_add(
        self, shortcut_group, shortcut_desc, shortcut_keys, action_name
    ):
        ...
