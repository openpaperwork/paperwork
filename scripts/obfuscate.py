#!/usr/bin/python

import curses.ascii
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
        print("  %s --> %s" % (i, t))
    print("==========================")


def clone_box(src_box, mapping):
    src_content = src_box.content
    dst_content = u""
    for char in src_content:
        if char in mapping:
            dst_content += mapping[char]
        else:
            dst_content += char
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


def clone_page_content(src_page, dst_page, mapping):
    src_boxes_lines = src_page.boxes
    dst_boxes_lines = []
    for src_boxes_line in src_boxes_lines:
        src_boxes = src_boxes_line.word_boxes
        dst_boxes_line = [clone_box(box, mapping) for box in src_boxes]
        dst_boxes_line = LineBox(dst_boxes_line, src_boxes_line.position)
        dst_boxes_lines.append(dst_boxes_line)
    dst_page.boxes = dst_boxes_lines
    dst_page.img = clone_img(src_page.img)


def clone_doc_content(src_doc, dst_doc, mapping):
    dst_pages = dst_doc.pages
    for src_page in src_doc.pages:
        dst_page = ImgPage(dst_doc)
        clone_page_content(src_page, dst_page, mapping)
        dst_pages.add(dst_page)
        sys.stdout.write("%d " % src_page.page_nb)
        sys.stdout.flush()


def main(src_dir, dst_dir):
    sys.stdout.write("Loading document %s ... " % src_dir)
    sys.stdout.flush()
    src_doc = ImgDoc(src_dir, os.path.basename(src_dir))
    sys.stdout.write("Done\n")

    sys.stdout.write("Analyzing document ... ")
    sys.stdout.flush()
    chars = get_chars(src_doc)
    sys.stdout.write("Done\n")

    sys.stdout.write("Generating char mapping ... ")
    sys.stdout.flush()
    mapping = generate_mapping(chars)
    sys.stdout.write("Done\n")

    print_mapping(mapping)

    os.mkdir(dst_dir)

    sys.stdout.write("Generating document %s ... " % dst_dir)
    sys.stdout.flush()
    dst_doc = ImgDoc(dst_dir, os.path.basename(dst_dir))
    clone_doc_content(src_doc, dst_doc, mapping)
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
        print("Each character will be replaced by another one (think Caesar"
              " cypher but slightly more complex)")
        print("")
        print("Example:")
        print("  %s ~/papers/20100730_0000_01 ~/tmp/20100730_0000_01.anonymized"
              % sys.argv[0])
        print("")
        print("WARNING:")
        print("  The obfuscation method used is NOT SAFE.")
        print("  Please censor manually confidential"
              " informations in .words *before* using this script.")
        print("  DO NOT post the result of this script publicly.")
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2]
    main(src, dst)
    sys.exit(0)
