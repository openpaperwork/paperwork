#!/usr/bin/env python3

from copy import copy
import multiprocessing
import sys
import threading

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Poppler', '0.18')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Gtk', '3.0')

from gi.repository import GObject

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


"""
Compare various image processing algorithm combinations with Tesseract
"""

STATS = {
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
        "ace",
        [
            pillowfight.ace,  # automatic color equalization
        ],
        copy(STATS),
    ),
    (
        "ace + unpaper",
        [
            pillowfight.ace,  # automatic color equalization
            pillowfight.unpaper_blackfilter,
            pillowfight.unpaper_noisefilter,
            pillowfight.unpaper_blurfilter,
            pillowfight.unpaper_masks,
            pillowfight.unpaper_grayfilter,
            pillowfight.unpaper_border,
        ],
        copy(STATS),
    ),
    (
        "ace + swt",
        [
            pillowfight.ace,  # automatic color equalization
            pillowfight.swt,  # Stroke Width Transformation
        ],
        copy(STATS),
    ),
    (
        "ace + unpaper + swt",
        [
            pillowfight.ace,  # automatic color equalization

            pillowfight.unpaper_blackfilter,
            pillowfight.unpaper_noisefilter,
            pillowfight.unpaper_blurfilter,
            pillowfight.unpaper_masks,
            pillowfight.unpaper_grayfilter,
            pillowfight.unpaper_border,

            pillowfight.swt,  # Stroke Width Transformation
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


class JobImageProcessing(Job):
    def __init__(self, factory, job_id, img_in, algos):
        super(JobImageProcessing, self).__init__(factory, job_id)
        self.img_in = img_in
        self.algos = algos

    def _add_score(self, txt, stats):
        for (word, word_pos) in g_tknzr(txt):
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
        print ("")
        print ("")
        print ("")
        print ("")
        print ("-" * 40)
        for algo in ALGORITHMS:
            stats = algo[2]
            print ("{}".format(algo[0]))
            sys.stdout.write("\t")
            for (name, value) in stats.items():
                sys.stdout.write("{}: {}   ".format(name, str(value).rjust(5)))
            sys.stdout.write("\n")
        print ("-" * 40)


    def do(self):
        img = self.img_in

        LOCK.acquire()
        try:
            img.load()
        finally:
            LOCK.release()

        for algo in self.algos[1]:
            img = algo(img)

        txt = OCR_TOOL.image_to_string(img)

        LOCK.acquire()
        try:
            self._add_score(txt, self.algos[2])
            self._print_stats()
        finally:
            LOCK.release()

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

    try:
        print ("Queueing jobs ...")
        nb_docs = 0
        nb_pages = 0
        for doc in dsearch.docs:
            nb_docs += 1
            for page in doc.pages:
                nb_pages += 1
                img = page.img
                for algos in ALGORITHMS:
                    job = factory.make(img, algos)
                    manager.schedule(job)

        print("Queued jobs : {} docs | {} pages".format(nb_docs, nb_pages))

        manager.wait_for_all()
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
