import logging

LOGGER = logging.getLogger(__name__)

try:
    import gi
    gi.require_version('Notify', '0.7')
    from gi.repository import Notify
    NOTIFY_AVAILABLE = True
except (ImportError, ValueError) as exc:
    LOGGER.error("Failed to import Notify", exc_info=exc)
    NOTIFY_AVAILABLE = False


import openpaperwork_core  # noqa E402
import openpaperwork_gtk.deps  # noqa E402


class NotifyBuilder(object):
    def __init__(self, title):
        self.title = title
        self.msg = None
        self.icon = None
        self.pixbuf = None
        self.actions = []
        self.notification = None

    def set_message(self, message):
        self.msg = message
        return self

    def set_icon(self, icon):
        self.icon = icon
        return self

    def add_action(self, action_id, label, callback, *args, **kwargs):
        self.actions.append((action_id, label, callback, args, kwargs))
        return self

    def set_image_from_pixbuf(self, pixbuf):
        self.pixbuf = pixbuf
        return self

    @staticmethod
    def _call_callback(notification, action, args):
        (callback, args, kwargs) = args
        return callback(*args, **kwargs)

    def show(self):
        self.notification = Notify.Notification.new(
            self.title, self.msg, self.icon
        )
        if self.pixbuf is not None:
            self.notification.set_image_from_pixbuf(self.pixbuf)
        for (action_id, label, callback, args, kwargs) in self.actions:
            self.notification.add_action(
                action_id, label,
                self._call_callback, (callback, args, kwargs)
            )
        self.notification.show()


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def __init__(self):
        # WORKAROUND(Jflesch): Keep a reference to the notifications.
        # Otherwise we never get the action from the user.
        self.notification_refs = []

    def get_interfaces(self):
        return [
            'chkdeps',
            'notifications',
        ]

    def get_deps(self):
        return [
        ]

    def init(self, core):
        super().init(core)
        if NOTIFY_AVAILABLE:
            Notify.init("Paperwork")

    def chkdeps(self, out: dict):
        if not NOTIFY_AVAILABLE:
            out['notify'].update(openpaperwork_gtk.deps.NOTIFY)

    def get_notification_builder(self, title, need_actions=False):
        caps = []
        if NOTIFY_AVAILABLE:
            caps = Notify.get_server_caps()
            if len(caps) <= 0:
                return None
        if not need_actions or "actions" in caps:
            r = NotifyBuilder(title)
            self.notification_refs.append(r)
            return r
        return None
