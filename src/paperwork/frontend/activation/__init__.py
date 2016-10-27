import logging
import os

import gettext
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from paperwork.frontend.util import load_uifile


_ = gettext.gettext
logger = logging.getLogger(__name__)


def to_bool(txt):
    if isinstance(txt, bool):
        return txt
    return txt.lower() == "true"


def get_os():
    return os.getenv("PAPERWORK_OS_NAME", os.name)


def is_activated(config):
    if get_os() != 'nt':
        return True
    # TODO
    return to_bool(os.getenv("PAPERWORK_ACTIVATED", False))


def has_expired(config):
    if get_os() != 'nt':
        return False
    expired = False
    # TODO
    return to_bool(os.getenv("PAPERWORK_EXPIRED", expired))


def get_remaining_days(config):
    remaining = 60
    # TODO
    return int(os.getenv("PAPERWORK_REMAINING", remaining))


class ActivationDialog(object):
    def __init__(self, main_win, config):
        widget_tree = load_uifile(
            os.path.join("activation", "activationdialog.glade"))

        self.dialog = widget_tree.get_object("dialogActivation")
        self.dialog.set_transient_for(main_win.window)
        self.dialog.connect("response", self.on_response_cb)

        self._config = config
        self._main_win = main_win

    def on_response_cb(self, widget, response):
        if response != 0:  # "Cancel"
            self.dialog.set_visible(False)
            self.dialog.destroy()
            self.dialog = None
            return True
        # "Ok"
        # TODO
        return True

    def show(self):
        self.dialog.set_visible(True)
