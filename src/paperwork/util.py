#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
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
"""
Various tiny functions that didn't fit anywhere else.
"""

import array
import os
import re
import StringIO
import unicodedata

import enchant
import enchant.tokenize
import Levenshtein
import cairo
import Image
import ImageDraw
import gettext
import glib
import gtk
import pycountry

_ = gettext.gettext

FORCED_SPLIT_KEYWORDS_REGEX = re.compile("[ '()]", re.UNICODE)
WISHED_SPLIT_KEYWORDS_REGEX = re.compile("[^\w!]", re.UNICODE)
MIN_KEYWORD_LEN = 3

UI_FILES_DIRS = [
    ".",
    "src/paperwork/frontend",
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
            print "Tried to use UI file %s but failed: %s" % (ui_file, str(exc))
            continue
        has_ui_file = True
        print "UI file used: " + ui_file
        break
    if not has_ui_file:
        raise Exception("Can't find resource file. Aborting")
    return widget_tree


def image2surface(img):
    if img == None:
        return None
    file_desc = StringIO.StringIO()
    img.save(file_desc, format="PNG")
    file_desc.seek(0)
    surface = cairo.ImageSurface.create_from_png(file_desc)
    return surface


def surface2image(surface):
    """
    Convert a cairo surface into a PIL image
    """
    if surface == None:
        return None
    img = Image.frombuffer("RGBA",
            (surface.get_width(), surface.get_height()),
            surface.get_data(), "raw", "BGRA", 0, 1)

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


def sizeof_fmt(num):
        STRINGS = [
            _('%3.1f bytes'),
            _('%3.1f KB'),
            _('%3.1f MB'),
            _('%3.1f GB'),
            _('%3.1f TB'),
        ]
        for string in STRINGS:
            if num < 1024.0:
                return string % (num)
            num /= 1024.0
        return STRINGS[-1] % (num)

def add_img_border(img, color="#a6a5a4"):
    img_draw = ImageDraw.Draw(img)
    img_draw.rectangle([(0, 0), (img.size[0]-1, img.size[1]-1)], outline=color)
    del img_draw
    return img

def check_spelling(ocr_lang, txt):
    """
    Check the spelling in the text, and compute a score. The score is the
    number of words correctly (or almost correctly) spelled.

    Returns:
        A tuple : (fixed text, score)
    """
    # Maximum distance from the first suggestion from python-enchant
    MAX_LEVENSHTEIN_DISTANCE = 1
    MIN_WORD_LEN = 4

    # TODO(Jflesch): We are assuming here that we can figure out the best
    # dictionary based on the 3 letters OCR lang. This is a bad assumption
    try:
        language = pycountry.languages.get(terminology=ocr_lang[:3])
    except KeyError:
        language = pycountry.languages.get(bibliographic=ocr_lang[:3])
    spelling_lang = language.alpha2

    words_dict = enchant.request_dict(spelling_lang)
    try:
        tknzr = enchant.tokenize.get_tokenizer(spelling_lang)
    except enchant.tokenize.TokenizerNotFoundError:
        # Fall back to default tokenization if no match for 'lang'
        tknzr = enchant.tokenize.get_tokenizer()

    score = 0
    offset = 0
    for (word, word_pos) in tknzr(txt):
        if words_dict.check(word):
            score += 1
            continue
        if len(word) < MIN_WORD_LEN:
            continue
        suggestions = words_dict.suggest(word)
        if (len(suggestions) <= 0):
            continue
        main_suggestion = suggestions[0]
        lv_dist = Levenshtein.distance(word, main_suggestion)
        if (lv_dist > MAX_LEVENSHTEIN_DISTANCE):
            continue

        print "Spell checking: Replacing: %s -> %s" % (word, main_suggestion)

        # let's replace the word by its suggestion

        pre_txt = txt[:word_pos + offset]
        post_txt = txt[word_pos + len(word) + offset:]
        txt = pre_txt + main_suggestion + post_txt
        offset += (len(main_suggestion) - len(word))

    return (txt, score)
