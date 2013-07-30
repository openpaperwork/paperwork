import logging

import gettext
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GdkPixbuf


_ = gettext.gettext
logger = logging.getLogger(__name__)


def popup_no_scanner_found(parent):
    """
    Show a popup to the user to tell them no scanner has been found
    """
    # TODO(Jflesch): should be in paperwork.frontend
    # Pyinsane doesn't return any specific exception :(
    logger.info("Showing popup !")
    msg = _("No scanner found (is your scanner turned on ?)")
    dialog = Gtk.MessageDialog(parent=parent,
                               flags=Gtk.DialogFlags.MODAL,
                               type=Gtk.MessageType.WARNING,
                               buttons=Gtk.ButtonsType.OK,
                               message_format=msg)
    dialog.run()
    dialog.destroy()


def ask_confirmation(parent):
    """
    Ask the user "Are you sure ?"

    Returns:
        True --- if they are
        False --- if they aren't
    """
    confirm = Gtk.MessageDialog(parent=parent,
                                flags=Gtk.DialogFlags.MODAL
                                | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.YES_NO,
                                message_format=_('Are you sure ?'))
    response = confirm.run()
    confirm.destroy()
    if response != Gtk.ResponseType.YES:
        logging.info("User cancelled")
        return False
    return True

