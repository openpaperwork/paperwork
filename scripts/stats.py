#!/usr/bin/env python

import sys

import paperwork.backend.config as config
import paperwork.backend.docsearch as docsearch
import paperwork.backend.util as util


def main():
    pconfig = config.PaperworkConfig()
    pconfig.read()
    print("Opening docs (%s)" % pconfig.settings['workdir'].value)
    print("====================")
    dsearch = docsearch.DocSearch(pconfig.settings['workdir'].value)

    nb_words = 0
    nb_docs = (len(dsearch.docs))
    nb_pages = 0
    max_pages = 0

    total_word_len = 0
    max_word_len = 0

    words = set()
    total_nb_unique_words = 0
    total_nb_unique_words_per_doc = 0

    print("")
    print("Analysis")
    print("========")

    all_labels = set([l.name for l in dsearch.label_list])
    label_keys = [ 'global', 'positive', 'negative' ]  # for the order
    total_label_accuracy = {
        'global': 0,
        'positive': 0,
        'negative': 0,
    }
    total_labels = {
        'global': 0,
        'positive': 0,
        'negative': 0,
    }

    for doc in dsearch.docs:
        sys.stdout.write(str(doc) + ": ")
        sys.stdout.flush()

        doc_words = set()

        if doc.nb_pages > max_pages:
            max_pages = doc.nb_pages

        ### Keyword stats
        for page in doc.pages:
            sys.stdout.write("%d " % (page.page_nb + 1))
            sys.stdout.flush()
            nb_pages += 1

            for line in page.text:
                for word in util.split_words(line):
                    # ignore words too short to be useful
                    if (len(word) < 4):
                        continue
                    if not word in words:
                        words.add(word)
                        total_nb_unique_words += 1
                    if not word in doc_words:
                        doc_words.add(word)
                        total_nb_unique_words_per_doc += 1

                    nb_words += 1
                    total_word_len += len(word)
                    if max_word_len < len(word):
                        max_word_len = len(word)

        ### Label predictions stats
        doc_labels = set([l.name for l in doc.labels])
        predicated_labels = set(dsearch.predict_label_list(doc))
        accurate = {
            'global': 0,
            'negative': 0,
            'positive': 0,
        }
        nb_labels = {
            'global': len(all_labels),
            'positive': len(doc_labels),
            'negative': len(all_labels) - len(doc_labels),
        }
        for key in label_keys:
            total_labels[key] += nb_labels[key]
        for label in all_labels:
            if not ((label in doc_labels) ^ (label in predicated_labels)):
                accurate['global'] += 1
                total_label_accuracy['global'] += 1
                if label in doc_labels:
                    accurate['positive'] += 1
                    total_label_accuracy['positive'] += 1
                else:
                    accurate['negative'] += 1
                    total_label_accuracy['negative'] += 1
        for key in label_keys:
            total = nb_labels[key]
            value = accurate[key]
            if total == 0:
                continue
            value = accurate[key]
            sys.stdout.write("\n\t- label prediction accuracy (%s): %d%%"
                             % (key, (100 * accurate[key] / total)))

        sys.stdout.write("\n")

    print("")
    print("Statistics")
    print("==========")
    print("Total number of documents: %d" % nb_docs)
    print("Total number of pages: %d" % nb_pages)
    print("Total number of words: %d" % nb_words)
    print("Total words len: %d" % total_word_len)
    print("Total number of unique words: %d" % total_nb_unique_words)
    print("===")
    print("Maximum number of pages in one document: %d" % max_pages)
    print("Maximum word length: %d" % max_word_len)
    print("Average word length: %f" % (float(total_word_len) / float(nb_words)))
    print ("Average number of words per page: %f"
           % (float(nb_words) / float(nb_pages)))
    print ("Average number of words per document: %f"
           % (float(nb_words) / float(nb_docs)))
    print ("Average number of pages per document: %f"
           % (float(nb_pages) / float(nb_docs)))
    print ("Average number of unique words per document: %f"
           % (float(total_nb_unique_words_per_doc) / float(nb_docs)))
    for key in label_keys:
        total = total_labels[key]
        value = total_label_accuracy[key]
        print ("Average accuracy of label prediction (%s): %d%%"
               % (key, (100 * value / total)))


if __name__ == "__main__":
    main()
