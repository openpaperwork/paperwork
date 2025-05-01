import abc


class AppAction(abc.ABC):
    pass


class AppActionCollector(abc.ABC):
    @abc.abstractmethod
    def app_actions_add(self, action):
        ...
