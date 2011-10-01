from util import SPLIT_KEYWORDS_REGEX

class WordBox(object):
    """
    Indicates where a specific word has been read on a page
    """

    MAX_PIXEL_DIST = 200

    def __init__(self, word):
        self.word = word
        self.position = None
        pass

    def add_char_box(self, box):
        box_position = box.get_position()
        if self.position == None:
            self.position = box_position
        else:
            if (self.position[0][0] < box_position[0][0]):
                a_x = self.position[0][0]
            else:
                a_x = box_position[0][0]
            if (self.position[0][1] < box_position[0][1]):
                a_y = self.position[0][1]
            else:
                a_y = box_position[0][1]
            if (self.position[1][0] > box_position[1][0]):
                b_x = self.position[1][0]
            else:
                b_x = box_position[1][0]
            if (self.position[1][1] > box_position[1][1]):
                b_y = self.position[1][1]
            else:
                b_y = box_position[1][1]
            self.position = ( (a_x, a_y), (b_x, b_y) )

    def get_word(self):
        return self.word

    def get_position(self):
        return self.position

def _get_char_boxes(word, char_boxes):
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
                if char_boxes[start_idx + l_idx].get_char().lower() != word[l_idx].lower():
                    full_match = False
                    break
            if full_match:
                end_idx = start_idx + len(word)
                break
    except IndexError, e:
        full_match = False
    if not full_match:
        print "Word %s not found in boxes" % (word)
        return None

    boxes = []
    for box_idx in range(start_idx, end_idx):
        boxes.append(char_boxes[box_idx])

    word_box = WordBox(word)
    for box in boxes:
        word_box.add_char_box(box)
        char_boxes.remove(box)
    return word_box

def get_word_boxes(text, char_boxes):
    char_box_idx = 0
    word_boxes = []

    for line in text:
        words = SPLIT_KEYWORDS_REGEX.split(line)

        for word in words:
            box = _get_char_boxes(word, char_boxes)
            if box == None:
                continue
            word_boxes.append(box)

    return word_boxes

