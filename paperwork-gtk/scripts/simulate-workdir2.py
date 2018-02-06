#!/usr/bin/env python3

import os
import tempfile

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Poppler', '0.18')

from paperwork_backend import config
from paperwork_backend import docimport
from paperwork_backend import docsearch
from paperwork_backend.util import rm_rf

"""
Create a work directory progressively, like a user would.
Uses an existing work directory for reference.
Compute statistics regarding label guessing

Scenario tested here:

for each document:
    - the user scan the first page
    - labels are guessed and added
    - user scans the remaining pages of the document
    - user fixes the labels
"""

g_correct_guess = 0
g_missing_guess = 0
g_wrong_guess = 0
g_nb_documents = 0
g_nb_src_labels = 0
g_nb_dst_labels = 0
g_perfect = 0


def upd_index(dst_dsearch, doc, new):
    index_updater = dst_dsearch.get_index_updater(optimize=False)
    if new:
        index_updater.add_doc(doc, index_update=False)
    else:
        index_updater.upd_doc(doc, index_update=False)
    index_updater.commit(index_update=False)


def label_guess(dst_dsearch, src_doc, dst_doc):
    """ Guess the labels, and apply the guess on the document """
    guessed_labels = dst_dsearch.guess_labels(dst_doc)

    for label in guessed_labels:
        dst_dsearch.add_label(dst_doc, label, update_index=False)
    upd_index(dst_dsearch, dst_doc, new=True)


def fix_labels(dst_dsearch, src_doc, dst_doc):
    """ Acts like the user fixing the labels """
    global g_nb_documents
    global g_correct_guess
    global g_missing_guess
    global g_wrong_guess
    global g_nb_src_labels
    global g_nb_dst_labels
    global g_perfect

    g_nb_documents += 1
    g_nb_src_labels += len(src_doc.labels)
    g_nb_dst_labels += len(dst_doc.labels)

    changed = False

    correct = 0
    missing = 0
    wrong = 0

    to_remove = set()
    to_add = set()

    for dst_label in dst_doc.labels:
        if dst_label not in src_doc.labels:
            g_wrong_guess += 1
            wrong += 1
            to_remove.add(dst_label)
            changed = True

    for label in to_remove:
        dst_dsearch.remove_label(dst_doc, label, update_index=False)

    for src_label in src_doc.labels:
        if src_label in dst_doc.labels:
            g_correct_guess += 1
            correct += 1
        else:
            g_missing_guess += 1
            missing += 1
            to_add.add(src_label)
            changed = True

    for label in to_add:
        if label not in dst_dsearch.labels.values():
            dst_dsearch.create_label(label)
        dst_dsearch.add_label(dst_doc, label, update_index=False)

    if changed:
        upd_index(dst_dsearch, dst_doc, new=False)
    else:
        g_perfect += 1

    out = u"success: {}%/{} || ".format(
        int(g_perfect * 100 / g_nb_documents),
        g_nb_documents
    )
    out += "ok: {}".format(correct)
    if missing:
        out += " / MISSING: {}".format(missing)
    if wrong:
        out += " / WRONG: {}".format(wrong)

    print (out)


def print_stats():
    global g_nb_documents
    global g_correct_guess
    global g_missing_guess
    global g_wrong_guess
    global g_nb_src_labels
    global g_nb_dst_labels
    global g_perfect

    # avoid division by zero
    if g_nb_src_labels == 0:
        g_nb_src_labels = -1
    if g_nb_dst_labels == 0:
        g_nb_dst_labels = -1
    nb_documents = g_nb_documents
    if nb_documents == 0:
        nb_documents += 1

    print ("---")
    print ("Success/total:            {}/{} = {}%".format(
        g_perfect, nb_documents,
        int(g_perfect * 100 / nb_documents)
    ))
    print ("Labels correctly guessed: {}/{} = {}%".format(
        g_correct_guess, g_nb_src_labels,
        int(g_correct_guess * 100 / g_nb_src_labels)
    ))
    print ("Labels not guessed:       {}/{} = {}%".format(
        g_missing_guess, g_nb_src_labels,
        int(g_missing_guess * 100 / g_nb_src_labels)
    ))
    print ("Labels wrongly guessed:   {}/{} = {}%".format(
        g_wrong_guess, g_nb_dst_labels,
        int(g_wrong_guess * 100 / g_nb_dst_labels)
    ))


def main():
    pconfig = config.PaperworkConfig()
    pconfig.read()

    src_dir = pconfig.settings['workdir'].value
    print ("Source work directory : {}".format(src_dir))
    src_dsearch = docsearch.DocSearch(src_dir)
    src_dsearch.reload_index()

    dst_doc_dir = tempfile.mkdtemp(suffix="paperwork-simulate-docs")
    dst_index_dir = tempfile.mkdtemp(suffix="paperwork-simulate-index")
    print (
        "Destination directories : {} | {}".format(dst_doc_dir, dst_index_dir)
    )
    dst_dsearch = docsearch.DocSearch(dst_doc_dir, indexdir=dst_index_dir)
    dst_dsearch.reload_index()

    try:
        documents = [x for x in src_dsearch.docs]
        documents.sort(key=lambda doc: doc.docid)

        for src_doc in documents:
            print("Document [{}]".format(src_doc.docid))
            files = os.listdir(src_doc.path)
            files.sort()

            current_doc = None
            dst_doc = None
            for filename in files:
                if "thumb" in filename:
                    continue
                filepath = os.path.join(src_doc.path, filename)
                fileuri = "file://" + filepath
                importers = docimport.get_possible_importers(
                    fileuri, current_doc=current_doc
                )
                if len(importers) <= 0:
                    continue
                assert(len(importers) == 1)
                importer = importers[0]
                (docs, page, new) = importer.import_doc(
                    fileuri, dst_dsearch, current_doc
                )
                dst_doc = docs[0]

                for page_nb in range(0, dst_doc.nb_pages):
                    if dst_doc.can_edit:
                        dst_doc.pages[page_nb].boxes = \
                            src_doc.pages[page_nb].boxes
                        dst_doc.pages[page_nb].drop_cache()

                if current_doc is None:
                    # first page --> guess labels and see if it matchs
                    label_guess(dst_dsearch, src_doc, dst_doc)
                else:
                    # just update the index
                    upd_index(dst_dsearch, dst_doc, new=False)

                current_doc = docs[0]

            if dst_doc is not None:
                fix_labels(dst_dsearch, src_doc, dst_doc)

    finally:
        rm_rf(dst_doc_dir)
        rm_rf(dst_index_dir)
        print_stats()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print ("Interrupted")
