import os
import re
import StringIO
import unicodedata

import glib
import gtk
import PIL
import pygtk

SPLIT_KEYWORDS_REGEX = re.compile("[^\w/*!-]", re.UNICODE)

def load_uifile(filename):
    """
    Load a .glade file and return the corresponding widget tree

    Arguments:
        filename -- glade filename to load. Must not contain any directory name, just the filename.
            This function will (try to) figure out where it must be found.

    Returns:
        GTK Widget tree

    Throws:
        Exception -- If the file cannot be found
    """
    UI_FILES_DIRS = [
        ".",
        "src",
        "/usr/local/share/paperwork",
        "/usr/share/paperwork",
    ]

    wTree = gtk.Builder()
    has_ui_file = False
    for ui_dir in UI_FILES_DIRS:
        ui_file = os.path.join(ui_dir, filename);
        try:
            wTree.add_from_file(ui_file)
        except glib.GError, e:
            print "Try to used UI file %s but failed: %s" % (ui_file, str(e))
            continue
        has_ui_file = True
        print "UI file used: " + ui_file
        break
    if not has_ui_file:
        raise Exception("Can't find ressource file. Aborting")
    return wTree

def strip_accents(s):
   return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

def gtk_refresh():
    while gtk.events_pending():
        gtk.main_iteration()

def image2pixbuf(im):
    fd = StringIO.StringIO()
    try:
        im.save(fd, "ppm")
        contents = fd.getvalue()
    finally:
        fd.close()
    loader = gtk.gdk.PixbufLoader("pnm")
    try:
        loader.write(contents, len(contents))
        pixbuf = loader.get_pixbuf()
    finally:
        loader.close()
    return pixbuf

