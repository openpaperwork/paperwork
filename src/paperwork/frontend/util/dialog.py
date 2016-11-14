#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

import logging

import gettext
from gi.repository import GLib
from gi.repository import Gtk


_ = gettext.gettext
logger = logging.getLogger(__name__)


def popup_no_scanner_found(parent, error_msg=None):
    """
    Show a popup to the user to tell them no scanner has been found
    """
    # TODO(Jflesch): should be in paperwork.frontend
    # Pyinsane doesn't return any specific exception :(
    logger.info("Showing popup !")
    if not error_msg:
        msg = _("Scanner not found (is your scanner turned on ?)")
    else:
        msg = _(
            "Scanner not found (is your scanner turned on ?) (error was: {})"
        )
        msg = msg.format(error_msg)
    dialog = Gtk.MessageDialog(parent=parent,
                               flags=Gtk.DialogFlags.MODAL,
                               message_type=Gtk.MessageType.WARNING,
                               buttons=Gtk.ButtonsType.OK,
                               text=msg)
    dialog.connect("response", lambda dialog, response:
                   GLib.idle_add(dialog.destroy))
    dialog.show_all()


def _ask_confirmation_goto_next(dialog, response, next_func):
    dialog.destroy()
    if response != Gtk.ResponseType.YES:
        logger.info("User cancelled")
        return
    logger.info("User validated")
    next_func()


def ask_confirmation(parent, next_func):
    """
    Ask the user "Are you sure ?"

    Returns:
        True --- if they are
        False --- if they aren't
    """
    logger.info("Asking user confirmation")
    confirm = Gtk.MessageDialog(parent=parent,
                                flags=Gtk.DialogFlags.MODAL
                                | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.YES_NO,
                                text=_('Are you sure ?'))
    confirm.connect("response",
                    lambda dialog, response: GLib.idle_add(
                        _ask_confirmation_goto_next, dialog, response, next_func
                    )
                )
    confirm.show_all()
    return True
