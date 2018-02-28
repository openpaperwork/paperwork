#!/usr/bin/env python3

import tempfile

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Poppler', '0.18')
gi.require_version('PangoCairo', '1.0')

from paperwork_backend import config  # noqa: E402
from paperwork_backend import docimport  # noqa: E402
from paperwork_backend import docsearch  # noqa: E402
from paperwork_backend import fs  # noqa: E402
from paperwork_backend.util import rm_rf  # noqa: E402

"""
Create a work directory progressively, like a user would.
Uses an existing work directory for reference.
Compute statistics regarding label guessing

Scenario tested here:

for each document:
    - the user scan the first page
    - labels are guessed and added
    - user fixes the labels
    - user scans the remaining pages of the document
"""

g_fs = fs.GioFileSystem()

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
        index_updater.add_doc(doc)
    else:
        index_updater.upd_doc(doc)
    index_updater.commit()


def label_guess(dst_dsearch, src_doc, dst_doc):
    """ Guess the labels, and apply the guess on the document """
    guessed_labels = dst_dsearch.guess_labels(dst_doc)
    guessed_labels = [label for (label, scores) in guessed_labels]

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
        if label not in dst_dsearch.label_list:
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

    print(out)


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

    print("---")
    print("Success/total:            {}/{} = {}%".format(
        g_perfect, nb_documents,
        int(g_perfect * 100 / nb_documents)
    ))
    print("Labels correctly guessed: {}/{} = {}%".format(
        g_correct_guess, g_nb_src_labels,
        int(g_correct_guess * 100 / g_nb_src_labels)
    ))
    print("Labels not guessed:       {}/{} = {}%".format(
        g_missing_guess, g_nb_src_labels,
        int(g_missing_guess * 100 / g_nb_src_labels)
    ))
    print("Labels wrongly guessed:   {}/{} = {}%".format(
        g_wrong_guess, g_nb_dst_labels,
        int(g_wrong_guess * 100 / g_nb_dst_labels)
    ))


def enable_logging():
    import logging
    l = logging.getLogger()
    s = logging.StreamHandler()
    l.addHandler(s)
    l.setLevel(logging.DEBUG)


def main():
    # enable_logging()
    pconfig = config.PaperworkConfig()
    pconfig.read()

    src_dir = pconfig.settings['workdir'].value
    print("Source work directory : {}".format(src_dir))
    src_dsearch = docsearch.DocSearch(src_dir, use_default_index_client=False)
    src_dsearch.reload_index()

    dst_doc_dir = tempfile.mkdtemp(suffix="paperwork-simulate-docs")
    dst_index_dir = tempfile.mkdtemp(suffix="paperwork-simulate-index")
    print(
        "Destination directories : {} | {}".format(dst_doc_dir, dst_index_dir)
    )
    dst_dsearch = docsearch.DocSearch(dst_doc_dir, indexdir=dst_index_dir,
                                      use_default_index_client=False)
    dst_dsearch.reload_index()

    print("Testing ...")

    try:
        documents = [x for x in src_dsearch.docs]
        documents.sort(key=lambda doc: doc.docid)

        print("Number of documents: {}".format(len(documents)))

        for src_doc in documents:
            print("Document [{}] | [{}]".format(src_doc.docid, src_doc.path))
            files = [x for x in g_fs.listdir(src_doc.path)]
            files.sort()

            current_doc = None
            for filepath in files:
                print("File: {}".format(filepath))
                filename = g_fs.basename(filepath)
                if "thumb" in filename or "labels" == filename:
                    continue
                importers = docimport.get_possible_importers(
                    [filepath], current_doc=current_doc
                )
                if len(importers) <= 0:
                    continue
                print("Importer(s): {}".format(", ".join([
                    str(x) for x in importers
                ])))
                assert(len(importers) == 1)
                importer = importers[0]
                result = importer.import_doc(
                    [filepath], dst_dsearch, current_doc
                )
                if current_doc is None:
                    dst_doc = result.new_docs[0]
                else:
                    dst_doc = current_doc

                for page_nb in range(0, dst_doc.nb_pages):
                    if dst_doc.can_edit:
                        dst_doc.pages[page_nb].boxes = \
                            src_doc.pages[page_nb].boxes

                if current_doc is None:
                    # first page --> guess labels and see if it matchs
                    label_guess(dst_dsearch, src_doc, dst_doc)
                    fix_labels(dst_dsearch, src_doc, dst_doc)
                else:
                    # just update the index
                    upd_index(dst_dsearch, dst_doc, new=False)

                current_doc = dst_doc

    finally:
        print("---")
        rm_rf(dst_doc_dir)
        rm_rf(dst_index_dir)
        print_stats()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
