#!/usr/bin/env python

import logging
import os

import gettext
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GdkPixbuf


_ = gettext.gettext
logger = logging.getLogger(__name__)

PREFIX = os.environ.get('VIRTUAL_ENV', '/usr')

UI_FILES_DIRS = [
    ".",
    "src/paperwork/frontend",
    PREFIX + "/share/paperwork",
    PREFIX + "/local/share/paperwork",
]


def load_uifile(filename):
    """
    Load a .glade file and return the corresponding widget tree

    Arguments:
        filename -- glade filename to load. Must not contain any directory
            name, just the filename. This function will (try to) figure out
            where it must be found.

    Returns:
        GTK Widget tree

    Throws:
        Exception -- If the file cannot be found
    """
    widget_tree = Gtk.Builder()
    has_ui_file = False
    for ui_dir in UI_FILES_DIRS:
        ui_file = os.path.join(ui_dir, filename)
        if os.access(ui_file, os.R_OK):
            logging.info("UI file used: " + ui_file)
            widget_tree.add_from_file(ui_file)
            has_ui_file = True
            break
    if not has_ui_file:
        logging.error("Can't find resource file '%s'. Aborting" % filename)
        raise Exception("Can't find resource file '%s'. Aborting" % filename)
    return widget_tree


_SIZEOF_FMT_STRINGS = [
    _('%3.1f bytes'),
    _('%3.1f KB'),
    _('%3.1f MB'),
    _('%3.1f GB'),
    _('%3.1f TB'),
]


def sizeof_fmt(num):
    """
    Format a number of bytes in a human readable way
    """
    for string in _SIZEOF_FMT_STRINGS:
        if num < 1024.0:
            return string % (num)
        num /= 1024.0
    return _SIZEOF_FMT_STRINGS[-1] % (num)
