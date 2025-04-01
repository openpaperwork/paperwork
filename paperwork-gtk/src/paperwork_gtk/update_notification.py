import random

import openpaperwork_core

from . import _


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'chkdeps',
            'update_listener',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'icon',
                'defaults': ['paperwork_gtk.icon'],
            },
            {
                'interface': 'notifications',
                'defaults': ['paperwork_gtk.notifications.notify'],
            },
            {
                'interface': 'update_detection',
                'defaults': ['paperwork_backend.beacon.update'],
            },
        ]

    def on_update_detected(self, local_version, remote_version):
        random_dumbnesses = [
            _("Now with 10% more freedom in it !"),
            _("Buy it now and get a 100% discount !"),
            _("New features and bugs available !"),
            _("New taste !"),
            _("We replaced your old bugs with new bugs. Enjoy."),
            _("Smarter, Better, Stronger"),
            # Linus Torvalds citation, look it up :)
            _("It's better when it's free."),
        ]

        notification = self.core.call_success(
            "get_notification_builder",
            _("A new version of Paperwork is available: {new_version}").format(
                new_version=".".join([str(x) for x in remote_version])
            )
        )
        if notification is None:
            return
        icon = self.core.call_success("icon_get_pixbuf", "paperwork", 32)
        notification.set_message(
            random.choice(random_dumbnesses)
        ).set_image_from_pixbuf(
            icon
        ).show()
