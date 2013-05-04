#!/usr/bin/env python

import sys

import paperwork.backend.config as config
import paperwork.backend.docsearch as docsearch
import paperwork.util as util

def main():
    print "Opening index"
    print "============="
    pconfig = config.PaperworkConfig()
    dsearch = docsearch.DocSearch(pconfig.workdir)

    nb_words = 0
    nb_docs = (len(dsearch.docs))
    nb_pages = 0

    total_word_len = 0
    max_word_len = 0

    print ""
    print "Analysis"
    print "========"

    for doc in dsearch.docs:
        sys.stdout.write(str(doc) + ": ")
        sys.stdout.flush()

        for page in doc.pages:
            sys.stdout.write("%d " % (page.page_nb + 1))
            sys.stdout.flush()
            nb_pages += 1

            for line in page.text:
                for word in util.split_words(line):
                    # ignore words too short to be useful
                    if (len(word) < 4):
                        continue
                    nb_words += 1
                    total_word_len += len(word)
                    if max_word_len < len(word):
                        max_word_len = len(word)

        sys.stdout.write("\n")

    print ""
    print "Statistics"
    print "=========="
    print "Total number of documents: %d" % nb_docs
    print "Total number of pages: %d" % nb_pages
    print "Total number of words: %d" % total_word_len
    print "==="
    print "Maximum word length: %d" % max_word_len
    print "Average word length: %f" % (float(total_word_len) / float(nb_words))
    print ("Average number of words per page: %f"
           % (float(nb_words) / float(nb_pages)))
    print ("Average number of words per document: %f"
           % (float(nb_words) / float(nb_docs)))
    print ("Average number of pages per document: %f"
           % (float(nb_pages) / float(nb_docs)))

if __name__ == "__main__":
    main()
