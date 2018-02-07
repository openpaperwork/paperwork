#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>

import ctypes
import errno
import io
import locale
import logging
import pycountry
import os
import re
import threading
import unicodedata

import PIL.Image

try:
    import cairo
    CAIRO_AVAILABLE = True
except:
    CAIRO_AVAILABLE = False

if os.name != "nt":
    import enchant
    import enchant.tokenize
    import Levenshtein


logger = logging.getLogger(__name__)
FORCED_SPLIT_KEYWORDS_REGEX = re.compile("[\n '()]", re.UNICODE)
WISHED_SPLIT_KEYWORDS_REGEX = re.compile("[^\w!]", re.UNICODE)

MIN_KEYWORD_LEN = 3

g_lock = threading.Lock()


def strip_accents(string):
    """
    Strip all the accents from the string
    """
    return u''.join(
        (character for character in unicodedata.normalize('NFD', string)
         if unicodedata.category(character) != 'Mn'))


def __cleanup_word_array(keywords):
    """
    Yield all the keywords long enough to be used
    """
    for word in keywords:
        if len(word) >= MIN_KEYWORD_LEN:
            yield word


def split_words(sentence, modify=True, keep_shorts=False):
    """
    Extract and yield the keywords from the sentence:
    - Drop keywords that are too short (keep_shorts=False)
    - Drop the accents (modify=True)
    - Make everything lower case (modify=True)
    - Try to separate the words as much as possible (using 2 list of
      separators, one being more complete than the others)
    """
    if (sentence == "*"):
        yield sentence
        return

    # TODO: i18n
    if modify:
        sentence = sentence.lower()
        sentence = strip_accents(sentence)

    words = FORCED_SPLIT_KEYWORDS_REGEX.split(sentence)
    if keep_shorts:
        word_iter = words
    else:
        word_iter = __cleanup_word_array(words)
    for word in word_iter:
        can_split = True
        can_yield = False
        subwords = WISHED_SPLIT_KEYWORDS_REGEX.split(word)
        for subword in subwords:
            if subword == "":
                continue
            can_yield = True
            if not keep_shorts and len(subword) < MIN_KEYWORD_LEN:
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


def dummy_progress_cb(progression, total, step=None, doc=None):
    """
    Dummy progression callback. Do nothing.
    """
    pass


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
    if os.name == "nt":
        assert(not "check_spelling() not available on Windows")
        return
    with _ENCHANT_LOCK:
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
            if (len(suggestions) <= 0):
                # this word is useless. It may even indicates a bad orientation
                score -= 10
                continue
            main_suggestion = suggestions[0]
            lv_dist = Levenshtein.distance(word, main_suggestion)
            if (lv_dist > _MAX_LEVENSHTEIN_DISTANCE):
                # hm, this word looks like it's in a bad shape
                continue

            logger.debug("Spell checking: Replacing: %s -> %s"
                         % (word, main_suggestion))

            # let's replace the word by its suggestion

            pre_txt = txt[:word_pos + offset]
            post_txt = txt[word_pos + len(word) + offset:]
            txt = pre_txt + main_suggestion + post_txt
            offset += (len(main_suggestion) - len(word))

            # fixed words may be a good hint for orientation
            score += 5

        return (txt, score)


def mkdir_p(path):
    """
    Act as 'mkdir -p' in the shell
    """
    try:
        os.makedirs(path)
    except OSError as exc:
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
                logger.info("Deleting file %s" % filepath)
                os.unlink(filepath)
            for dirname in dirs:
                dirpath = os.path.join(root, dirname)
                if os.path.islink(dirpath):
                    logger.info("Deleting link %s" % dirpath)
                    os.unlink(dirpath)
                else:
                    logger.info("Deleting dir %s" % dirpath)
                    os.rmdir(dirpath)
        logger.info("Deleting dir %s", path)
        os.rmdir(path)


def surface2image(surface):
    """
    Convert a cairo surface into a PIL image
    """
    # TODO(Jflesch): Python 3 problem
    # cairo.ImageSurface.get_data() raises NotImplementedYet ...

    # import PIL.ImageDraw
    #
    # if surface is None:
    #     return None
    # dimension = (surface.get_width(), surface.get_height())
    # img = PIL.Image.frombuffer("RGBA", dimension,
    #                            surface.get_data(), "raw", "BGRA", 0, 1)
    #
    # background = PIL.Image.new("RGB", img.size, (255, 255, 255))
    # background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    # return background

    global g_lock
    with g_lock:
        img_io = io.BytesIO()
        surface.write_to_png(img_io)
        img_io.seek(0)
        img = PIL.Image.open(img_io)
        img.load()

        if "A" not in img.getbands():
            return img

        img_no_alpha = PIL.Image.new("RGB", img.size, (255, 255, 255))
        img_no_alpha.paste(img, mask=img.split()[3])  # 3 is the alpha channel
        return img_no_alpha


def image2surface(img):
    """
    Convert a PIL image into a Cairo surface
    """
    if not CAIRO_AVAILABLE:
        raise Exception("Cairo not available(). image2surface() cannot work.")

    # TODO(Jflesch): Python 3 problem
    # cairo.ImageSurface.create_for_data() raises NotImplementedYet ...

    # img.putalpha(256)
    # (width, height) = img.size
    # imgd = img.tobytes('raw', 'BGRA')
    # imga = array.array('B', imgd)
    # stride = width * 4
    #  return cairo.ImageSurface.create_for_data(
    #      imga, cairo.FORMAT_ARGB32, width, height, stride)

    # So we fall back to this method:
    global g_lock
    with g_lock:
        img_io = io.BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)
        return cairo.ImageSurface.create_from_png(img_io)


def find_language(lang_str=None, allow_none=False):
    if lang_str is None:
        lang_str = locale.getdefaultlocale()[0]
        if lang_str is None and not allow_none:
            logger.warning("Unable to figure out locale. Assuming english !")
            return find_language('eng')
        if lang_str is None:
            logger.warning("Unable to figure out locale !")
            return None

    lang_str = lang_str.lower()
    if "_" in lang_str:
        lang_str = lang_str.split("_")[0]

    try:
        return pycountry.pycountry.languages.get(name=lang_str.title())
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(iso_639_3_code=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(iso639_3_code=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(iso639_2T_code=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(iso639_1_code=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(terminology=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(bibliographic=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(alpha_3=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(alpha_2=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    try:
        return pycountry.pycountry.languages.get(alpha2=lang_str)
    except (KeyError, UnicodeDecodeError):
        pass
    if allow_none:
        logger.warning("Unknown language [{}]".format(lang_str))
        return None
    if lang_str is not None and lang_str == 'eng':
        raise Exception("Unable to find language !")
    logger.warning("Unknown language [{}]. Switching back to english".format(
        lang_str
    ))
    return find_language('eng')


def hide_file(filepath):
    if os.name != 'nt':
        # win32 only
        return
    logger.info("Hiding file: {}".format(filepath))
    ret = ctypes.windll.kernel32.SetFileAttributesW(
        filepath, 0x02  # hidden
    )
    if not ret:
        raise ctypes.WinError()
