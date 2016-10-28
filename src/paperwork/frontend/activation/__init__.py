import logging
import os
import re

import gettext
from gi.repository import GLib
from gi.repository import Gtk

from paperwork.frontend.util import load_uifile
from paperwork.frontend.util.actions import SimpleAction


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


class ActionFormatKey(SimpleAction):
    def __init__(self, entry):
        super().__init__("Format key")
        self.entry = entry
        self.is_editing = False
        self.check_char = re.compile("[0-9a-zA-Z+/]")

    def do(self):
        super().do()
        if self.is_editing:
            # avoid recursion
            return
        # so the position of the cursor has already been updated when we are
        # called
        GLib.idle_add(self._do)

    def _do(self):
        CHUNK_LENGTH = 5

        key = self.entry.get_text()
        pos = self.entry.get_position()
        logger.info("Key before processing: [{}] ({})".format(key, pos))

        new_key = ""
        # make sure each CHUNK_LENGTH characters, we have a '-'
        idx = 0
        for char in key:
            if idx % CHUNK_LENGTH == 0 and idx != 0:
                if char != '-':
                    new_key += '-'
                    pos += 1
                new_key += char
            elif self.check_char.match(char):
                new_key += char
            else:
                pos -= 1
            idx += 1

        logger.info("Key after processing: [{}]".format(new_key))

        self.is_editing = True
        try:
            self.entry.set_text(new_key)
            self.entry.set_position(pos)
        finally:
            self.is_editing = False


class ActivationDialog(object):
    def __init__(self, main_win, config):
        widget_tree = load_uifile(
            os.path.join("activation", "activationdialog.glade"))

        self.dialog = widget_tree.get_object("dialogActivation")
        self.dialog.set_transient_for(main_win.window)
        self.dialog.connect("response", self.on_response_cb)

        self._config = config
        self._main_win = main_win

        key_entry = widget_tree.get_object("entryKey")
        self.key_action = ActionFormatKey(key_entry)
        self.key_action.connect([key_entry])

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
