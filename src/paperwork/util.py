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

import errno
import os
import re
import logging
import StringIO
import threading
import unicodedata

import cairo
import enchant
import enchant.tokenize
import gettext
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GdkPixbuf
import nltk.metrics.distance
import PIL.Image
import PIL.ImageDraw

import pyinsane.abstract_th as pyinsane

_ = gettext.gettext
logger = logging.getLogger(__name__)

FORCED_SPLIT_KEYWORDS_REGEX = re.compile("[ '()]", re.UNICODE)
WISHED_SPLIT_KEYWORDS_REGEX = re.compile("[^\w!]", re.UNICODE)
MIN_KEYWORD_LEN = 3

PREFIX = os.environ.get('VIRTUAL_ENV', '/usr')

UI_FILES_DIRS = [
    ".",
    "src/paperwork/frontend",
    PREFIX + "/share/paperwork",
    PREFIX + "/local/share/paperwork",
]


def strip_accents(string):
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
    - Try to separate the words as much as possible (using 2 list of
      separators, one being more complete than the others)
    """
    if (sentence == "*"):
        yield sentence
        return

    # TODO: i18n
    sentence = sentence.lower()
    sentence = strip_accents(sentence)

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
                if subword[0] == '"':
                    subword = subword[1:]
                if subword[-1] == '"':
                    subword = subword[:-1]
                yield subword
        elif can_yield:
            if word[0] == '"':
                word = word[1:]
            if word[-1] == '"':
                word = word[:-1]
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


def image2surface(img):
    """
    Convert a PIL image into a Cairo surface
    """
    if img is None:
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
    if surface is None:
        return None
    dimension = (surface.get_width(), surface.get_height())
    img = PIL.Image.frombuffer("RGBA", dimension,
                           surface.get_data(), "raw", "BGRA", 0, 1)

    background = PIL.Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    return background


def image2pixbuf(img):
    """
    Convert an image object to a gdk pixbuf
    """
    if img is None:
        return None
    file_desc = StringIO.StringIO()
    try:
        img.save(file_desc, "ppm")
        contents = file_desc.getvalue()
    finally:
        file_desc.close()
    loader = GdkPixbuf.PixbufLoader.new_with_type("pnm")
    try:
        loader.write(contents)
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
    """
    Show a popup to the user to tell them no scanner has been found
    """
    # TODO(Jflesch): should be in paperwork.frontend
    # Pyinsane doesn't return any specific exception :(
    logger.info("Showing popup !")
    msg = _("No scanner found (is your scanner turned on ?)")
    dialog = Gtk.MessageDialog(parent=parent,
                               flags=Gtk.DialogFlags.MODAL,
                               message_type=Gtk.MessageType.WARNING,
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
                                message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.YES_NO,
                                message_format=_('Are you sure ?'))
    response = confirm.run()
    confirm.destroy()
    if response != Gtk.ResponseType.YES:
        logging.info("User cancelled")
        return False
    return True


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


def add_img_border(img, color="#a6a5a4", width=1):
    """
    Add a border of the specified color and width around a PIL image
    """
    img_draw = PIL.ImageDraw.Draw(img)
    for line in range(0, width):
        img_draw.rectangle([(line, line), (img.size[0]-1-line,
                                           img.size[1]-1-line)],
                           outline=color)
    del img_draw
    return img


_ENCHANT_LOCK = threading.Lock()
_MAX_LEVENSHTEIN_DISTANCE = 1
_MIN_WORD_LEN = 4


def check_spelling(spelling_lang, txt):
    """
    Check the spelling in the text, and compute a score. The score is the
    number of words correctly (or almost correctly) spelled, minus the number
    of mispelled words. Words "almost" correct remains neutral (-> are not
    included in the score)

    Returns:
        A tuple : (fixed text, score)
    """
    _ENCHANT_LOCK.acquire()
    try:
        # Maximum distance from the first suggestion from python-enchant

        words_dict = enchant.request_dict(spelling_lang)
        try:
            tknzr = enchant.tokenize.get_tokenizer(spelling_lang)
        except enchant.tokenize.TokenizerNotFoundError:
            # Fall back to default tokenization if no match for 'lang'
            tknzr = enchant.tokenize.get_tokenizer()

        score = 0
        offset = 0
        for (word, word_pos) in tknzr(txt):
            if len(word) < _MIN_WORD_LEN:
                continue
            if words_dict.check(word):
                # immediately correct words are a really good hint for
                # orientation
                score += 100
                continue
            suggestions = words_dict.suggest(word)
            if len(suggestions) <= 0:
                # this word is useless. It may even indicates a bad orientation
                score -= 10
                continue
            main_suggestion = suggestions[0]
            lv_dist = nltk.metrics.distance.edit_distance(word, main_suggestion)
            if lv_dist > _MAX_LEVENSHTEIN_DISTANCE:
                # hm, this word looks like it's in a bad shape
                continue

            logging.debug("Spell checking: Replacing: %s -> %s"
                   % (word, main_suggestion))

            # let's replace the word by its suggestion

            pre_txt = txt[:word_pos + offset]
            post_txt = txt[word_pos + len(word) + offset:]
            txt = pre_txt + main_suggestion + post_txt
            offset += (len(main_suggestion) - len(word))

            # fixed words may be a good hint for orientation
            score += 5

        return (txt, score)
    finally:
        _ENCHANT_LOCK.release()


def mkdir_p(path):
    """
    Act as 'mkdir -p' in the shell
    """
    try:
        os.makedirs(path)
    except OSError, exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def rm_rf(path):
    """
    Act as 'rm -rf' in the shell
    """
    if os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for filename in files:
                filepath = os.path.join(root, filename)
                logging.info("Deleting file %s" % filepath)
                os.unlink(filepath)
            for dirname in dirs:
                dirpath = os.path.join(root, dirname)
                logging.info("Deleting dir %s" % dirpath)
                os.rmdir(dirpath)
        os.rmdir(path)


def set_scanner_opt(scanner_opt_name, scanner_opt, possible_values):
    """
    Set one of the scanner options

    Arguments:
        scanner_opt_name --- for verbose
        scanner_opt --- the scanner option (its value, its constraints, etc)
        possible_values --- a list of values considered valid (the first one
                            being the preferred one)
    """
    value = possible_values[0]
    regexs = [re.compile(x, flags=re.IGNORECASE) for x in possible_values]

    if (scanner_opt.constraint_type ==
        pyinsane.SaneConstraintType.STRING_LIST):
        value = None
        for regex in regexs:
            for constraint in scanner_opt.constraint:
                if regex.match(constraint):
                    value = constraint
                    break
            if value is not None:
                break
        if value is None:
            raise pyinsane.SaneException(
                "%s are not a valid values for option %s"
                % (str(possible_values), scanner_opt_name))

    logger.info("Setting scanner option '%s' to '%s'"
                % (scanner_opt_name, str(value)))
    scanner_opt.value = value


def __set_scan_area_pos(options, opt_name, select_value_func, missing_options):
    if not opt_name in options:
        missing_options.append(opt_name)
    constraint = options[opt_name].constraint
    if isinstance(constraint, tuple):
        value = select_value_func(constraint[0], constraint[1])
    else:  # is an array
        value = select_value_func(constraint)
    options[opt_name].value = value


def maximize_scan_area(scanner):
    opts = scanner.options
    missing_opts = []
    __set_scan_area_pos(opts, "tl-x", min, missing_opts)
    __set_scan_area_pos(opts, "tl-y", min, missing_opts)
    __set_scan_area_pos(opts, "br-x", max, missing_opts)
    __set_scan_area_pos(opts, "br-y", max, missing_opts)
    if missing_opts:
        logger.warning("Failed to maximize the scan area. Missing options: %s"
                       % ", ".join(missing_opts))
