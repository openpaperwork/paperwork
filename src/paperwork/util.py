"""
Various tiny functions that didn't fit anywhere else.
"""

import os
import re
import StringIO
import unicodedata

import Image
import gettext
import glib
import gtk

_ = gettext.gettext

FORCED_SPLIT_KEYWORDS_REGEX = re.compile("[ '()]", re.UNICODE)
WISHED_SPLIT_KEYWORDS_REGEX = re.compile("[^\w!]", re.UNICODE)
MIN_KEYWORD_LEN = 3

UI_FILES_DIRS = [
    ".",
    "src/paperwork/view",
    "/usr/local/share/paperwork",
    "/usr/share/paperwork",
]


def __strip_accents(string):
    """
    Strip all the accents from the string
    """
    return ''.join(
        (character for character in unicodedata.normalize('NFD', string)
         if unicodedata.category(character) != 'Mn'))


def __cleanup_word_array(keywords):
    """
    Yield all the keywords long enough to be used
    """
    for word in keywords:
        if len(word) >= MIN_KEYWORD_LEN:
            yield word


def split_words(sentence):
    """
    Extract and yield the keywords from the sentence:
    - Drop keywords that are too short
    - Drop the accents
    - Make everything lower case
    - Try to separate the words as much as possible (using 2 list of separators,
    one being more complete than the others)
    """
    if (sentence == "*"):
        yield sentence
        return

    # TODO: i18n
    sentence = sentence.lower()
    sentence = __strip_accents(sentence)

    words = FORCED_SPLIT_KEYWORDS_REGEX.split(sentence)
    for word in __cleanup_word_array(words):
        can_split = True
        can_yield = False
        subwords = WISHED_SPLIT_KEYWORDS_REGEX.split(word)
        for subword in subwords:
            if subword == "":
                continue
            can_yield = True
            if len(subword) < MIN_KEYWORD_LEN:
                can_split = False
                break
        if can_split:
            for subword in subwords:
                if subword == "":
                    continue
                yield subword
        elif can_yield:
            yield word


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
    widget_tree = gtk.Builder()
    has_ui_file = False
    for ui_dir in UI_FILES_DIRS:
        ui_file = os.path.join(ui_dir, filename)
        try:
            widget_tree.add_from_file(ui_file)
        except glib.GError, exc:
            print "Try to used UI file %s but failed: %s" % (ui_file, str(exc))
            continue
        has_ui_file = True
        print "UI file used: " + ui_file
        break
    if not has_ui_file:
        raise Exception("Can't find ressource file. Aborting")
    return widget_tree


def surface2image(surface):
    """
    Convert a cairo surface into a PIL image
    """
    if surface == None:
        return None
    img = Image.frombuffer("RGBA",
            (surface.get_width(), surface.get_height()),
            surface.get_data(), "raw", "RGBA", 0, 1)

    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3]) # 3 is the alpha channel
    return background



def image2pixbuf(img):
    """
    Convert an image object to a gdk pixbuf
    """
    if img == None:
        return None
    file_desc = StringIO.StringIO()
    try:
        img.save(file_desc, "ppm")
        contents = file_desc.getvalue()
    finally:
        file_desc.close()
    loader = gtk.gdk.PixbufLoader("pnm")
    try:
        loader.write(contents, len(contents))
        pixbuf = loader.get_pixbuf()
    finally:
        loader.close()
    return pixbuf

def dummy_progress_cb(progression, total, step=None, doc=None):
    """
    Dummy progression callback. Do nothing.
    """
    pass

def popup_no_scanner_found(parent):
    # Pyinsane doesn't return any specific exception :(
    print "Showing popup !"
    msg = _("No scanner found (is your scanner turned on ?)")
    dialog = gtk.MessageDialog(parent=parent,
                               flags=gtk.DIALOG_MODAL,
                               type=gtk.MESSAGE_WARNING,
                               buttons=gtk.BUTTONS_OK,
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
    confirm = gtk.MessageDialog(parent=parent,
                                flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                type=gtk.MESSAGE_WARNING,
                                buttons=gtk.BUTTONS_YES_NO,
                                message_format=_('Are you sure ?'))
    response = confirm.run()
    confirm.destroy()
    if response != gtk.RESPONSE_YES:
        print "User cancelled"
        return False
    return True
