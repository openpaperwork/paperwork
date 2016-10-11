#!/usr/bin/env python3

import csv
import os
import multiprocessing
import multiprocessing.pool
import sys
import tempfile
import traceback
import threading

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
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
    - user fixes the labels
    - user scans the remaining pages of the document
"""


g_lock = threading.Lock()


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


def fix_labels(stats, dst_dsearch, src_doc, dst_doc):
    """ Acts like the user fixing the labels """
    stats['nb_documents'] += 1
    stats['nb_src_labels'] += len(src_doc.labels)
    stats['nb_dst_labels'] += len(dst_doc.labels)

    changed = False

    correct = 0
    missing = 0
    wrong = 0

    to_remove = set()
    to_add = set()

    for dst_label in dst_doc.labels:
        if dst_label not in src_doc.labels:
            stats['wrong_guess'] += 1
            wrong += 1
            to_remove.add(dst_label)
            changed = True

    for label in to_remove:
        dst_dsearch.remove_label(dst_doc, label, update_index=False)

    for src_label in src_doc.labels:
        if src_label in dst_doc.labels:
            stats['correct_guess'] += 1
            correct += 1
        else:
            stats['missing_guess'] += 1
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
        stats['perfect'] += 1

    g_lock.acquire()
    try:
        print("Document [{}|{}]".format(
            dst_dsearch.label_guesser.yes_diff_ratio,
            src_doc.docid
        ))

        out = u"success: {}%/{} || ".format(
            int(stats['perfect'] * 100 / stats['nb_documents']),
            stats['nb_documents']
        )
        out += "ok: {}".format(correct)
        if missing:
            out += " / MISSING: {}".format(missing)
        if wrong:
            out += " / WRONG: {}".format(wrong)
    finally:
        g_lock.release()

    print(out)


def print_stats(stats):
    # avoid division by zero
    if stats['nb_src_labels'] == 0:
        stats['nb_src_labels'] = -1
    if stats['nb_dst_labels'] == 0:
        stats['nb_dst_labels'] = -1
    nb_documents = stats['nb_documents']
    if nb_documents == 0:
        nb_documents += 1

    g_lock.acquire()
    try:
        print("---")
        print("Success/total:            {}/{} = {}%".format(
            stats['perfect'], nb_documents,
            int(stats['perfect'] * 100 / nb_documents)
        ))
        print("Labels correctly guessed: {}/{} = {}%".format(
            stats['correct_guess'], stats['nb_src_labels'],
            int(stats['correct_guess'] * 100 / stats['nb_src_labels'])
        ))
        print("Labels not guessed:       {}/{} = {}%".format(
            stats['missing_guess'], stats['nb_src_labels'],
            int(stats['missing_guess'] * 100 / stats['nb_src_labels'])
        ))
        print("Labels wrongly guessed:   {}/{} = {}%".format(
            stats['wrong_guess'], stats['nb_dst_labels'],
            int(stats['wrong_guess'] * 100 / stats['nb_dst_labels'])
        ))
    finally:
        g_lock.release()


def run_simulation(
    src_dsearch,
    yes_diff_ratio,
    csvwriter
):
    stats = {
        'nb_documents': 0,
        'correct_guess': 0,
        'missing_guess': 0,
        'wrong_guess': 0,
        'nb_src_labels': 0,
        'nb_dst_labels': 0,
        'perfect': 0,
    }

    dst_doc_dir = tempfile.mkdtemp(suffix="paperwork-simulate-docs")
    dst_index_dir = tempfile.mkdtemp(suffix="paperwork-simulate-index")
    print(
        "Destination directories : {} | {}".format(dst_doc_dir, dst_index_dir)
    )
    dst_dsearch = docsearch.DocSearch(dst_doc_dir, indexdir=dst_index_dir)
    dst_dsearch.reload_index()

    dst_dsearch.label_guesser.yes_diff_ratio = yes_diff_ratio

    try:
        documents = [x for x in src_dsearch.docs]
        documents.sort(key=lambda doc: doc.docid)

        for src_doc in documents:
            files = os.listdir(src_doc.path)
            files.sort()

            current_doc = None
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
                    fix_labels(stats, dst_dsearch, src_doc, dst_doc)
                else:
                    # just update the index
                    upd_index(dst_dsearch, dst_doc, new=False)

                current_doc = docs[0]
    finally:
        g_lock.acquire()
        try:
            csvwriter.writerow([
                yes_diff_ratio,
                stats['nb_documents'], stats['perfect'],
            ])
        finally:
            g_lock.release()
        rm_rf(dst_doc_dir)
        rm_rf(dst_index_dir)
        print_stats(stats)


def _run_simulation(*args):
    try:
        run_simulation(*args)
    except Exception as exc:
        print("EXCEPTION: {}".format(exc))
        traceback.print_exc()
        raise


def main():
    if len(sys.argv) < 3:
        print("Syntax:")
        print(
            "  {} [yes_diff_ratios] [out_csv_file]".format(
                sys.argv[0]
            )
        )
        sys.exit(1)

    yes_diff_ratios = eval(sys.argv[1])
    out_csv_file = sys.argv[2]

    pconfig = config.PaperworkConfig()
    pconfig.read()

    src_dir = pconfig.settings['workdir'].value
    print("Source work directory : {}".format(src_dir))
    src_dsearch = docsearch.DocSearch(src_dir)
    src_dsearch.reload_index()

    nb_threads = multiprocessing.cpu_count()
    pool = multiprocessing.pool.ThreadPool(processes=nb_threads)

    with open(out_csv_file, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        for ratio in yes_diff_ratios:
            pool.apply_async(
                _run_simulation,
                (src_dsearch, ratio, csvwriter,)
            )
        pool.close()
        pool.join()
    print("All done !")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
