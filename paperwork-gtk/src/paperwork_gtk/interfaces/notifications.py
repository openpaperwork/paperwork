import abc


class AbstractNotificationBuilder(abc.ABC):
    @abc.abstractmethod
    def set_message(self, message):
        ...

    @abc.abstractmethod
    def set_icon(self, icon):
        ...

    @abc.abstractmethod
    def add_action(self, action_id, label, callback, *args, **kwargs):
        ...

    @abc.abstractmethod
    def set_image_from_pixbuf(self, pixbuf):
        ...

    @abc.abstractmethod
    def show(self):
        ...


class Notifications(abc.ABC):
    @abc.abstractmethod
    def get_notification_builder(self, title, need_actions=False) -> AbstractNotificationBuilder:
        ...
