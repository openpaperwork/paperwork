"""
Code to guess word boxes (ie rectangles) from characters boxes + the text.
"""

from util import dummy_progress_cb
from util import SPLIT_KEYWORDS_REGEX

WORDBOX_GUESSING = 'Word box guessing'

class WordBox(object):
    """
    Indicates where a specific word has been read on a page
    """

    MAX_PIXEL_DIST = 200

    def __init__(self, word):
        self.word = word
        self.position = None

    def add_char_box(self, box):
        """
        Add a character box to this word box.
        """
        if self.position == None:
            self.position = box.position
        else:
            if (self.position[0][0] < box.position[0][0]):
                a_x = self.position[0][0]
            else:
                a_x = box.position[0][0]
            if (self.position[0][1] < box.position[0][1]):
                a_y = self.position[0][1]
            else:
                a_y = box.position[0][1]
            if (self.position[1][0] > box.position[1][0]):
                b_x = self.position[1][0]
            else:
                b_x = box.position[1][0]
            if (self.position[1][1] > box.position[1][1]):
                b_y = self.position[1][1]
            else:
                b_y = box.position[1][1]
            self.position = ((a_x, a_y), (b_x, b_y))


def __get_char_boxes(word, char_boxes):
    """
    Look for the box of the word 'word', using the given char_boxes. Note that
    once the word is found, the used character boxes will be removed from
    char_boxes.

    Arguments:
        word --- the word for which we are looking for its box
        char_boxes --- all the remaining character boxes, up to now

    Returns:
        The word box. None if not found.
    """
    start_idx = 0
    end_idx = 0
    l_idx = 0

    if len(word) <= 0:
        return None
    if len(char_boxes) <= 0:
        return None

    try:
        for start_idx in range(0, len(char_boxes)):
            full_match = True
            for l_idx in range(0, len(word)):
                if (char_boxes[start_idx + l_idx].char.lower()
                    != word[l_idx].lower()):
                    full_match = False
                    break
            if full_match:
                end_idx = start_idx + len(word)
                break
    except IndexError:
        full_match = False
    if not full_match:
        #print "Word %s not found in boxes" % (word)
        return None

    boxes = []
    for box_idx in range(start_idx, end_idx):
        boxes.append(char_boxes[box_idx])

    word_box = WordBox(word)
    for box in boxes:
        word_box.add_char_box(box)
        char_boxes.remove(box)
    return word_box


def get_word_boxes(text, char_boxes, callback=dummy_progress_cb):
    """
    Try to deduce the word boxes, based on a text and character boxes (see
    tesseract.TesseractBox). This process may take time. This is why this
    function takes a progression callback as argument.

    Arguments:
        text --- array of lines
        char_boxes --- tesseract.TesseractBox
        callback --- progression callback (see dummy_progress_cb)
    """
    word_boxes = []

    callback(0, len(text), WORDBOX_GUESSING)
    progression = 0

    for line in text:
        words = SPLIT_KEYWORDS_REGEX.split(line)

        for word in words:
            box = __get_char_boxes(word, char_boxes)
            if box == None:
                continue
            word_boxes.append(box)
        progression += 1
        callback(progression, len(text), WORDBOX_GUESSING)

    callback(len(text), len(text), WORDBOX_GUESSING)
    return word_boxes
