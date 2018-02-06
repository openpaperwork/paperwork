#!/usr/bin/env python3

from copy import copy
import gc
import multiprocessing
import sys
import datetime
import threading

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Poppler', '0.18')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Gtk', '3.0')

import enchant
import enchant.tokenize
import Levenshtein
import pillowfight
import pyocr

from paperwork_backend import config
from paperwork_backend import docsearch

from paperwork.frontend.util.jobs import Job
from paperwork.frontend.util.jobs import JobFactory
from paperwork.frontend.util.jobs import JobScheduler

from gi.repository import GObject


"""
Compare various image processing algorithm combinations with Tesseract
"""

STATS = {
    "nb_pages": 0,
    "nb_words": 0,
    "too_short": 0,  # Maybe garbage if there are a lot
    "perfect": 0,  # direct hit in Enchant's dictionnary
    "garbage": 0,  # no suggestion at all from enchant
    "correctable": 0,  # clear match
    "maybe": 0,  # some suggestions, but no clear match
}

ALGORITHMS = [
    (
        "raw",
        [],
        copy(STATS),
    ),
    (
        "unpaper",
        [
            (pillowfight.unpaper_blackfilter, {}),
            (pillowfight.unpaper_noisefilter, {}),
            (pillowfight.unpaper_blurfilter, {}),
            (pillowfight.unpaper_masks, {}),
            (pillowfight.unpaper_grayfilter, {}),
            (pillowfight.unpaper_border, {}),
        ],
        copy(STATS),
    ),
    (
        "swt",
        [
            # Stroke Width Transformation
            (
                pillowfight.swt,
                {'output_type': pillowfight.SWT_OUTPUT_ORIGINAL_BOXES}
            ),
        ],
        copy(STATS),
    ),
    (
        "unpaper + swt",
        [
            (pillowfight.unpaper_blackfilter, {}),
            (pillowfight.unpaper_noisefilter, {}),
            (pillowfight.unpaper_blurfilter, {}),
            (pillowfight.unpaper_masks, {}),
            (pillowfight.unpaper_grayfilter, {}),
            (pillowfight.unpaper_border, {}),

            # Stroke Width Transformation
            (
                pillowfight.swt,
                {'output_type': pillowfight.SWT_OUTPUT_ORIGINAL_BOXES}
            ),
        ],
        copy(STATS),
    ),
    (
        "ace",
        [
            # automatic color equalization
            (pillowfight.ace, {'seed': 0xDEADBEE}),
        ],
        copy(STATS),
    ),
    (
        "ace + unpaper",
        [
            # automatic color equalization
            (pillowfight.ace, {'seed': 0xDEADBEE}),
            (pillowfight.unpaper_blackfilter, {}),
            (pillowfight.unpaper_noisefilter, {}),
            (pillowfight.unpaper_blurfilter, {}),
            (pillowfight.unpaper_masks, {}),
            (pillowfight.unpaper_grayfilter, {}),
            (pillowfight.unpaper_border, {}),
        ],
        copy(STATS),
    ),
    (
        "ace + swt",
        [
            # automatic color equalization
            (pillowfight.ace, {'seed': 0xDEADBEE}),
            # Stroke Width Transformation
            (
                pillowfight.swt,
                {'output_type': pillowfight.SWT_OUTPUT_ORIGINAL_BOXES}
            ),
        ],
        copy(STATS),
    ),
    (
        "ace + unpaper + swt",
        [
            # automatic color equalization
            (pillowfight.ace, {'seed': 0xDEADBEE}),

            (pillowfight.unpaper_blackfilter, {}),
            (pillowfight.unpaper_noisefilter, {}),
            (pillowfight.unpaper_blurfilter, {}),
            (pillowfight.unpaper_masks, {}),
            (pillowfight.unpaper_grayfilter, {}),
            (pillowfight.unpaper_border, {}),

            # Stroke Width Transformation
            (
                pillowfight.swt,
                {'output_type': pillowfight.SWT_OUTPUT_ORIGINAL_BOXES}
            ),
        ],
        copy(STATS),
    ),
]

OCR_TOOL = pyocr.get_available_tools()[0]

LOCK = threading.Lock()

MAX_LEVENSHTEIN_DISTANCE = 1
MIN_WORD_LEN = 4

g_lang = "eng"
g_dictionnary = None
g_tknzr = None
g_nb_total_pages = 0
g_start_time = None


class JobImageProcessing(Job):
    def __init__(self, factory, job_id, page_in, algos):
        super(JobImageProcessing, self).__init__(factory, job_id)
        self.page_in = page_in
        self.algos = algos

    def _add_score(self, txt, stats):
        stats['nb_pages'] += 1
        for (word, word_pos) in g_tknzr(txt):
            stats['nb_words'] += 1
            if len(word) < MIN_WORD_LEN:
                stats['too_short'] += 1
                continue
            if g_dictionnary.check(word):
                stats['perfect'] += 1
                continue
            suggestions = g_dictionnary.suggest(word)
            if len(suggestions) <= 0:
                stats['garbage'] += 1
                continue
            main_suggestion = suggestions[0]
            lv_dist = Levenshtein.distance(word, main_suggestion)
            if (lv_dist <= MAX_LEVENSHTEIN_DISTANCE):
                stats['correctable'] += 1
                continue
            stats['maybe'] += 1

    def _print_stats(self):
        print ("-" * 40)
        for algo in ALGORITHMS:
            stats = algo[2]
            print ("{}".format(algo[0]))
            sys.stdout.write("  ")
            for (name, value) in stats.items():
                if not name.startswith("nb_"):
                    sys.stdout.write("{}: {} ({}%) | ".format(
                        name, str(value).rjust(5),
                        str(int(
                            value * 100 / max(1, stats['nb_words'])
                        )).rjust(3)
                    ))
                else:
                    sys.stdout.write("{}: {} | ".format(
                        name, str(value).rjust(5)
                    ))
            sys.stdout.write("\n")
        print ("-" * 40)

    def do(self):
        with LOCK:
            img = self.page_in.img
            img.load()

        for (algo, kwargs) in self.algos[1]:
            img = algo(img, **kwargs)

        txt = OCR_TOOL.image_to_string(img)

        with LOCK:
            self._add_score(txt, self.algos[2])

            stats = self.algos[2]

            current_time = datetime.datetime.now()
            elapsed_time = current_time - g_start_time
            time_per_document = elapsed_time / stats['nb_pages']
            eta = time_per_document * (g_nb_total_pages - stats['nb_pages'])

            print ("")
            print ("")
            print ("")
            print ("")
            print ("Done: {} ({}/{} = {}% ==> ETA: {})".format(
                self.page_in,
                stats['nb_pages'], g_nb_total_pages,
                int(stats['nb_pages'] * 100 / g_nb_total_pages),
                current_time + eta
            ))
            self._print_stats()

            gc.collect()

GObject.type_register(JobImageProcessing)


class JobFactoryImageProcessing(JobFactory):
    def __init__(self, name="img_processing"):
        super(JobFactoryImageProcessing, self).__init__(name)

    def make(self, img_in, algos):
        job = JobImageProcessing(
            self, next(self.id_generator),
            img_in, algos
        )
        return job


class WorkerManager(object):
    def __init__(self, nb_workers=multiprocessing.cpu_count()):
        if (len(ALGORITHMS) % nb_workers) == 0:  # for correct dispatch
            nb_workers += 1
        self.nb_workers = nb_workers
        self.schedulers = [
            JobScheduler("{}".format(nb)) for nb in range(0, self.nb_workers)
        ]
        for scheduler in self.schedulers:
            scheduler.warnings = False
        self.last_scheduler = 0

    def start(self):
        for scheduler in self.schedulers:
            scheduler.start()

    def schedule(self, job):
        """ Distribute jobs across schedulers """
        self.schedulers[self.last_scheduler].schedule(job)
        self.last_scheduler += 1
        self.last_scheduler %= len(self.schedulers)

    def wait_for_all(self):
        for scheduler in self.schedulers:
            scheduler.wait_for_all()

    def stop(self):
        for scheduler in self.schedulers:
            scheduler.stop()


def main():
    global g_lang
    global g_dictionnary
    global g_tknzr
    global g_nb_total_pages
    global g_start_time

    print ("Will use {} for OCR".format(OCR_TOOL.get_name()))

    print ("Initializing dictionnary ...")
    g_lang = "eng"
    if len(sys.argv) > 1:
        g_lang = "fra"

    g_dictionnary = enchant.request_dict(g_lang[:2])
    try:
        g_tknzr = enchant.tokenize.get_tokenizer(g_lang[:2])
    except enchant.tokenize.TokenizerNotFoundError as exc:
        print("Warning: Falling back to default tokenizer ({})".format(exc))
        g_tknzr = enchant.tokenize.get_tokenizer()
    print ("Done")

    print ("Loading documents list ...")
    pconfig = config.PaperworkConfig()
    pconfig.read()
    work_dir = pconfig.settings['workdir'].value
    dsearch = docsearch.DocSearch(work_dir)
    dsearch.reload_index()
    print ("Documents loaded")
    print ("")

    print ("Initalizing workers ...")
    manager = WorkerManager()
    manager.start()

    factory = JobFactoryImageProcessing()
    print ("Done")

    g_start_time = datetime.datetime.now()

    try:
        print ("Queueing jobs ...")
        nb_docs = 0
        nb_pages = 0
        for doc in dsearch.docs:
            if not doc.can_edit:  # probably not an OCR-ized doc
                continue
            nb_docs += 1
            for page in doc.pages:
                if not page.can_edit:  # probably not an OCR-ized page
                    continue
                nb_pages += 1
                g_nb_total_pages += 1
                for algos in ALGORITHMS:
                    job = factory.make(page, algos)
                    manager.schedule(job)

        print("Queued jobs : {} docs | {} pages".format(nb_docs, nb_pages))

        manager.wait_for_all()
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
