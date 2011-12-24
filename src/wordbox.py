"""
Code to guess word boxes (ie rectangles) from characters boxes + the text.
"""

from util import dummy_progress_cb
from util import split_words

WORDBOX_GUESSING = 'Word box guessing'


class WordBox(object):
    """
    Indicates where a specific word has been read on a page
    """

    MAX_PIXEL_DIST = 200

    def __init__(self, word):
        words = split_words(word)
        self.word = " ".join(words)
        self.__word_hash = hash(word)
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

    def __hash__(self):
        return self.__word_hash


class CharBox(object):
    """
    Wrapper for TesseractBox. Used to make a link list of TesseractBox.
    """

    def __init__(self, tesseract_box):
        self.tesseract_box = tesseract_box
        self.next_box = None
        self.end_of_word = False


def __get_char_boxes(word, char_boxes):
    """
    Look for the box of the word 'word', using the given char_boxes. Note that
    once the word is found, the used character boxes will be removed from
    char_boxes.

    Arguments:
        word --- the word for which we are looking for its box
        char_boxes --- A linked list of all the remaining character boxes
            (CharBox), up to now

    Returns:
        The word box. None if not found.
    """
    prev_start_char = None
    start_char = char_boxes
    end_char = None
    l_idx = 0
    full_match = False

    if len(word) <= 0:
        return (char_boxes, None)
    if char_boxes == None:
        return (char_boxes, None)

    while start_char != None:
        full_match = True
        end_char = start_char
        l_idx = 0
        for l_idx in range(0, len(word)):
            if end_char == None or end_char.tesseract_box.char != word[l_idx]:
                full_match = False
                break
            if end_char.end_of_word and l_idx < (len(word) - 1):
                full_match = False
                break
            l_idx += 1
            end_char = end_char.next_box
        if full_match:
            break
        prev_start_char = start_char
        start_char = start_char.next_box
    if not full_match:
        return (char_boxes, None)

    word_box = WordBox(word)

    while start_char != end_char:
        word_box.add_char_box(start_char.tesseract_box)
        # drop the current char from the list
        if prev_start_char == None:
            char_boxes = start_char.next_box
        else:
            prev_start_char.next_box = start_char.next_box
            prev_start_char.end_of_word = True
        prev_start_char = start_char
        start_char = start_char.next_box

    return (char_boxes, word_box)


def get_word_boxes(text, tesseract_boxes, callback=dummy_progress_cb):
    """
    Try to deduce the word boxes, based on a text and character boxes (see
    tesseract.TesseractBox). This process may take time. This is why this
    function takes a progression callback as argument.

    Arguments:
        text --- array of lines
        char_boxes --- tesseract.TesseractBox
        callback --- progression callback (see dummy_progress_cb)
    """
    char_boxes = None

    for box in reversed(tesseract_boxes):
        new_box = CharBox(box)
        new_box.next_box = char_boxes
        char_boxes = new_box

    word_boxes = []

    callback(0, len(text), WORDBOX_GUESSING)
    progression = 0

    for line in text:
        # Do not use split_words() here ! It does more than spliting.
        words = line.split(" ")

        for word in words:
            (char_boxes, box) = __get_char_boxes(word, char_boxes)
            if box == None:
                continue
            word_boxes.append(box)
        progression += 1
        callback(progression, len(text), WORDBOX_GUESSING)

    callback(len(text), len(text), WORDBOX_GUESSING)
    return word_boxes
