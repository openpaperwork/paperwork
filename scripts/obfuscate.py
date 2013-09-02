#!/usr/bin/python

import curses.ascii
import hashlib
import random
import sys
import os

from PIL import Image
from PIL import ImageDraw

from pyocr.builders import Box
from pyocr.builders import LineBox

from paperwork.backend import config
from paperwork.backend import docsearch
from paperwork.backend import util
from paperwork.backend.img.doc import ImgDoc
from paperwork.backend.img.page import ImgPage


def get_chars(doc):
    chars = set()
    for page in doc.pages:
        for line in page.text:
            for char in line:
                if char == u"\n":
                    continue
                chars.add(char)
    return chars


def gen_salt():
    alphabet = [chr(x) for x in xrange(ord("0"), ord("9"))]
    alphabet += [chr(x) for x in xrange(ord("a"), ord("z"))]
    alphabet += [chr(x) for x in xrange(ord("A"), ord("Z"))]
    chars=[]
    for i in xrange(512):
        chars.append(random.choice(alphabet))
    return "".join(chars)


def generate_mapping(chars):
    # make sure we have some basic chars in the set
    for rng in [
            xrange(ord('a'), ord('z')),
            xrange(ord('A'), ord('Z')),
            xrange(ord('0'), ord('9')),
        ]:
        for ch in rng:
            chars.add(chr(ch))

    chars = [x for x in chars]
    chars.sort()
    shuffled = chars[:]
    random.shuffle(shuffled)

    mapping = {}
    for char_idx in xrange(0, len(chars)):
        mapping[chars[char_idx]] = shuffled[char_idx]
    return mapping


def print_mapping(mapping):
    print("==========================")
    print("Mapping that will be used:")
    for (i, t) in mapping.iteritems():
        print("  %s --> %s" % (i.encode("utf-8"), t.encode("utf-8")))
    print("==========================")


def clone_box(src_box, mapping, salt):
    src_content = src_box.content

    content = u""
    for char in src_content:
        if char in mapping:
            content += mapping[char]
        else:
            content += char

    content_hash = hashlib.sha512()
    content_hash.update(salt)
    content_hash.update(content.encode("utf-8"))

    dst_content = u""
    sha = content_hash.digest()
    for char_pos in xrange(0, len(src_content)):
        if not src_content[char_pos] in mapping:
            dst_content += char
        char = ord(sha[char_pos])
        char_idx = char % len(mapping)
        dst_content += mapping.values()[char_idx]

    dst_content = dst_content[:len(src_content)]

    return Box(dst_content, src_box.position)


def clone_img(src_img):
    # we just reuse the size
    img_size = src_img.size
    dst_img = Image.new("RGB", img_size, color="#ffffff")
    draw = ImageDraw.Draw(dst_img)
    if img_size[0] > 200 and img_size[1] > 200:
        draw.rectangle((100, 100, img_size[0] - 100, img_size[1] - 100),
                       fill="#333333")
        draw.line((100, 100, img_size[0] - 100, img_size[1] - 100),
                  fill="#ffffff", width=5)
        draw.line((img_size[0] - 100, 100,
                        100, img_size[1] - 100),
                  fill="#ffffff", width=5)
    return dst_img


def clone_page_content(src_page, dst_page, mapping, salt):
    src_boxes_lines = src_page.boxes
    dst_boxes_lines = []
    for src_boxes_line in src_boxes_lines:
        src_boxes = src_boxes_line.word_boxes
        dst_boxes_line = [clone_box(box, mapping, salt) for box in src_boxes]
        dst_boxes_line = LineBox(dst_boxes_line, src_boxes_line.position)
        dst_boxes_lines.append(dst_boxes_line)
    dst_page.boxes = dst_boxes_lines
    dst_page.img = clone_img(src_page.img)


def clone_doc_content(src_doc, dst_doc, mapping, salt):
    dst_pages = dst_doc.pages
    for src_page in src_doc.pages:
        dst_page = ImgPage(dst_doc)
        clone_page_content(src_page, dst_page, mapping, salt)
        dst_pages.add(dst_page)
        sys.stdout.write("%d " % src_page.page_nb)
        sys.stdout.flush()


def main(src_dir, dst_dir):
    sys.stdout.write("Loading document %s ... " % src_dir)
    sys.stdout.flush()
    src_doc = ImgDoc(src_dir, os.path.basename(src_dir))
    sys.stdout.write("Done\n")

    if (src_doc.nb_pages <= 0):
        raise Exception("No pages found. Is this an image doc ?")

    sys.stdout.write("Analyzing document ... ")
    sys.stdout.flush()
    chars = get_chars(src_doc)
    sys.stdout.write("Done\n")

    sys.stdout.write("Generating salt ... ")
    sys.stdout.flush()
    salt = gen_salt()
    sys.stdout.write("Done\n")
    print("Will use [%s] as salt for the hash" % salt)

    sys.stdout.write("Generating char mapping ... ")
    sys.stdout.flush()
    mapping = generate_mapping(chars)
    sys.stdout.write("Done\n")

    print_mapping(mapping)

    os.mkdir(dst_dir)

    sys.stdout.write("Generating document %s ... " % dst_dir)
    sys.stdout.flush()
    dst_doc = ImgDoc(dst_dir, os.path.basename(dst_dir))
    clone_doc_content(src_doc, dst_doc, mapping, salt)
    sys.stdout.write("... Done\n")

    print("All done")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage:")
        print("  %s <src_dir> <out_dir>" % sys.argv[0])
        print("")
        print("  src_dir : document to anonymize")
        print("  out_dir : directory in which to write the anonymized version")
        print("")
        print("Images will be replaced by a dummy image")
        print("Words are replaced by pieces of their hash (SHA512)")
        print("")
        print("Example:")
        print("  %s ~/papers/20100730_0000_01 ~/tmp/20100730_0000_01.anonymized"
              % sys.argv[0])
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2]
    main(src, dst)
    sys.exit(0)
