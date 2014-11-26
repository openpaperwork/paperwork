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

import array
import errno
import logging
import os
import re
import threading
import unicodedata

import enchant
import enchant.tokenize
import Levenshtein

logger = logging.getLogger(__name__)
FORCED_SPLIT_KEYWORDS_REGEX = re.compile("[ '()]", re.UNICODE)
WISHED_SPLIT_KEYWORDS_REGEX = re.compile("[^\w!]", re.UNICODE)

MIN_KEYWORD_LEN = 3


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
            if (len(suggestions) <= 0):
                # this word is useless. It may even indicates a bad orientation
                score -= 10
                continue
            main_suggestion = suggestions[0]
            lv_dist = Levenshtein.distance(word, main_suggestion)
            if (lv_dist > _MAX_LEVENSHTEIN_DISTANCE):
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
                logging.info("Deleting file %s" % filepath)
                os.unlink(filepath)
            for dirname in dirs:
                dirpath = os.path.join(root, dirname)
                logging.info("Deleting dir %s" % dirpath)
                os.rmdir(dirpath)
        os.rmdir(path)


def surface2image(surface):
    """
    Convert a cairo surface into a PIL image
    """
    import PIL.Image
    import PIL.ImageDraw

    if surface is None:
        return None
    dimension = (surface.get_width(), surface.get_height())
    img = PIL.Image.frombuffer("RGBA", dimension,
                               surface.get_data(), "raw", "BGRA", 0, 1)

    background = PIL.Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    return background


def image2surface(img):
    """
    Convert a PIL image into a Cairo surface
    """
    import cairo

    img.putalpha(256)
    (width, height) = img.size
    imgd = img.tobytes('raw', 'BGRA')
    imga = array.array('B', imgd)
    stride = width * 4
    return cairo.ImageSurface.create_for_data(
        imga, cairo.FORMAT_ARGB32, width, height, stride)
