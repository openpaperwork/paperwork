import base64
import logging
import pickle
import os
import re

import gettext
from gi.repository import GLib
from gi.repository import Gtk

from paperwork.frontend.util import load_uifile
from paperwork.frontend.util.actions import SimpleAction


def get_os():
    return os.getenv("PAPERWORK_OS_NAME", os.name)


if get_os() == 'nt':
    from Crypto.Hash import SHA
    from Crypto.PublicKey import ElGamal


_ = gettext.gettext
logger = logging.getLogger(__name__)


def strip_base64(text):
    text = text.strip()
    text = text.strip(b"=")
    text = text.replace(b"\n", b"")
    return text


def pad_base64(data):
    """
    Activation keys are encoded in base64, but the padding is removed
    to make them shorter. We re-add it here.
    """
    data = data.replace(b"\n", b"")
    missing = len(data) % 4
    if missing == 0:
        return data
    data += (b'=' * (4 - missing))
    return data


def unserialize_elgamal_key(key):
    key = pad_base64(key)
    key = base64.decodebytes(key)
    key = pickle.loads(key)
    return ElGamal.construct((key['p'], key['g'], key['y']))


def check_activation_key(activation_key, email):
    """
    Returns:
        None --- if OK
        a string --- message telling what's wrong
    """
    # We use ElGamal signature to forge and check the activation keys.
    # As you can guess from the key length and the signature length,
    # this is not secure *at* *all*, and this is not the point.
    #
    # Activation process is just a reminder to pay for the Windows version.
    # If you're smart enough to break this crappy private key here, you are
    # smart enough to build your own version of Paperwork for Windows.

    public_key = \
        b"gAN9cQAoWAEAAAB5cQFKbZDQClgBAAAAZ3ECSq6eZXtYAQAAAHBxA4oFj0ovuQB1Lg"
    public_key = unserialize_elgamal_key(public_key)
    activation_key = activation_key.encode("utf-8")
    email = b"" if email is None else email.encode("utf-8")

    if len(activation_key) < 10:
        return _("Invalid activation key (too short)")

    sig_type = activation_key[:1]
    payload = activation_key[:6]
    signature = activation_key[6:]

    if sig_type != b"E" and sig_type != b"I":
        return _("Invalid activation key (bad prefix: {})").format(
            sig_type.decode("utf-8")
        )

    if sig_type == b"E":
        # email has been hashed and the beginning of the hash of the email
        # is the signed payload
        h = SHA.new(email).digest()
        h = base64.encodebytes(h)
        h = strip_base64(h)
        if h[:5] != payload[1:]:
            return _("Email does not match the activation key")

    # sig_type == b"I" means we signed the invoice number, but I don't want
    # to annoy users by asking it back here.
    # (we ask the email here just to be really clear the activation key is
    # tied to their email address, and so it is personal)

    h = SHA.new(payload).digest()

    signature = pad_base64(signature)
    signature = base64.decodebytes(signature)
    try:
        signature = pickle.loads(signature)
    except EOFError:
        return _("Invalid activation key (too short)")

    if not public_key.verify(h, signature):
        return _("Invalid activation key")

    return None


def to_bool(txt):
    if isinstance(txt, bool):
        return txt
    return txt.lower() == "true"


def is_activated(config):
    # Just add 'return True' here to disable this whole thingie.
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
                    idx += 1
                new_key += char
                if char == '-':
                    idx = 0
            elif self.check_char.match(char):
                new_key += char
                idx += 1
            else:
                pos -= 1

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

        self.key_entry = widget_tree.get_object("entryKey")
        self.email_entry = widget_tree.get_object("entryEmail")
        self.key_action = ActionFormatKey(self.key_entry)
        self.key_action.connect([self.key_entry])

        self.label_error = widget_tree.get_object("labelError")

    def on_response_cb(self, widget, response):
        if response != 0:  # "Cancel"
            self.dialog.set_visible(False)
            self.dialog.destroy()
            self.dialog = None
            return True
        # "Ok"
        key = self.key_entry.get_text().replace("-", "").strip()
        email = self.email_entry.get_text().strip()
        error = check_activation_key(key, email)
        logger.info("Checking activation key: [{}]/[{}]".format(key, email))
        if not error:
            logger.info("Activation key ok !")
            # TODO: Write it in the configuration
            msg = _("Activation successful. Please restart Paperwork")
            dialog = Gtk.MessageDialog(
                parent=self.dialog,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=msg)
            dialog.run()
            dialog.destroy()
            self.dialog.set_visible(False)
            self.dialog.destroy()
            self.dialog = None
            return True
        logger.info("Invalid key: {}".format(error))
        self.label_error.set_text(error)
        return True

    def show(self):
        self.dialog.set_visible(True)
