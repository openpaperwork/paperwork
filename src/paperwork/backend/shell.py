import os
import sys

import gi

gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Poppler', '0.18')

from gi.repository import GLib

from . import config
from . import docimport
from . import docsearch


def is_verbose():
    return os.environ['PAPERWORK_VERBOSE'] != ""


def is_interactive():
    return os.environ['PAPERWORK_INTERACTIVE'] != ""


def get_docsearch():
    pconfig = config.PaperworkConfig()
    pconfig.read()

    if is_verbose():
        print ("Work directory: {}".format(pconfig.settings['workdir'].value))

    dsearch = docsearch.DocSearch(pconfig.settings['workdir'].value)
    dsearch.reload_index()
    return dsearch


def _dump_page(page):
    for line in page.boxes:
        out = ""
        for word in line.word_boxes:
            out += word.content + " "
        print (out.strip())


def cmd_dump(docid, page_nb=None):
    """
    Arguments: <document id> [<page number>]
    Dump the content of the specified document.
    Beware, page numbers start from 1.
    See 'search' for the document ids.
    """
    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    if page_nb:
        page = doc.pages[int(page_nb) - 1]
        _dump_page(page)
    else:
        for page in doc.pages:
            print ("=== Page {} ===".format(page.page_nb + 1))
            _dump_page(page)


def _get_importer(filepath, doc):
    fileuri = GLib.filename_to_uri(filepath)
    importers = docimport.get_possible_importers(fileuri, current_doc=doc)

    if len(importers) < 0:
        raise Exception("Don't know how to import {}".format(filepath))
    if len(importers) == 1:
        return importers[0]
    elif not is_interactive():
        raise Exception(
            "Many way to import {} and running in batch mode".format(
                filepath
            )
        )
    else:
        print("Import of {}:")
        for (idx, importer) in enumerate(importers):
            print ("{} - {}".format(idx, importer))
        idx = input("? ")
        return importers[int(idx)]


def _do_import(filepaths, dsearch, doc, guess_labels=True):
    index_updater = dsearch.get_index_updater(optimize=False)

    for filepath in filepaths:
        if not os.path.exists(filepath):
            raise FileNotFoundError(filepath)  # NOQA (Python 3.x only)
        fileuri = GLib.filename_to_uri(filepath)
        importer = _get_importer(filepath, doc)
        if is_verbose():
            print ("File {}: Importer = {}".format(filepath, importer))
        (docs, page, is_new_doc) = importer.import_doc(
            fileuri, dsearch, current_doc=doc
        )
        if docs is None or len(docs) <= 0:
            print ("File {} already imported".format(filepath))
        else:
            for doc in docs:
                if is_new_doc and guess_labels:
                    labels = dsearch.guess_labels(doc)
                    for label in labels:
                        dsearch.add_label(doc, label, update_index=False)
                print("File {} --> Document {} (labels: {})".format(
                    filepath, doc.docid,
                    ", ".join([label.name for label in doc.labels])
                ))
                if is_new_doc:
                    index_updater.add_doc(doc)
                else:
                    index_updater.upd_doc(doc)

    if is_verbose():
        print ("Updating index ...")
    index_updater.commit()
    if is_verbose():
        print ("Done")


def cmd_import(*args):
    """
    Arguments: <file_or_folder> [--no_label_guessing] [--append <document_id>]
    Import a file or a PDF folder.
    """
    guess_labels = True
    docid = None
    doc = None

    if "--no_label_guessing" in args:
        guess_labels = False
        args.remove("--guess_labels")
    if "--append" in args:
        idx = args.index("--append")
        docid = args[idx + 1]
        args.remove("--append")
        args.remove(docid)
    if len(args) <= 0:
        sys.stderr.write("Nothing to import.\n")
        return

    dsearch = get_docsearch()

    if docid:
        doc = dsearch.get(docid)
        if doc is None:
            sys.stderr.write("Document {} not found\n".format(docid))
            return

    return _do_import(args, dsearch, doc, guess_labels)


class RescanManager(object):
    def __init__(self):
        self.dsearch = get_docsearch()
        self.verbose = is_verbose()
        self.dexaminer = self.dsearch.get_doc_examiner()
        self.index_updater = self.dsearch.get_index_updater()

    def _on_new_doc(self, doc):
        self.index_updater.add_doc(doc)
        if self.verbose:
            print ("New document: {}".format(doc.docid))

    def _on_upd_doc(self, doc):
        self.index_updater.upd_doc(doc)
        self.changes['upd'].add(doc)
        if self.verbose:
            print ("Updated document: {}".format(doc.docid))

    def _on_del_doc(self, doc):
        self.index_updater.del_doc(doc)
        if self.verbose:
            print ("Deleted document: {}".format(doc.docid))

    def _on_doc_unchanged(self, doc):
        pass

    def _on_progress(self, progression, total, step=None, doc=None):
        if not self.verbose:
            return
        if progression % 10 != 0:
            return
        progression /= total
        current = ""
        if doc:
            current = "({})".format(doc.docid)
        sys.stdout.write("\b" * 100)
        sys.stdout.write(
            "{}[{}{}] {}% {}".format(
                "\b" * 100,
                "=" * int(10 * progression),
                " " * int(10 - (10 * progression)),
                int(progression * 100),
                current
            )
        )
        sys.stdout.flush()

    def rescan(self):
        self.dexaminer.examine_rootdir(
            self._on_new_doc,
            self._on_upd_doc,
            self._on_del_doc,
            self._on_doc_unchanged,
            self._on_progress
        )
        if self.verbose:
            sys.stdout.write("\b" * 100 + " " * 100)
            sys.stdout.write("\b" * 100)
            print ("Rewriting index ...")
        self.index_updater.commit()
        if self.verbose:
            print ("Done")


def cmd_rescan():
    """
    Rescan the work directory. Look for new, updated or deleted documents
    and update the index accordingly.
    """
    rm = RescanManager()
    rm.rescan()


def _get_first_line(doc):
    out = ""
    for page in doc.pages:
        lines = page.boxes
        for line in lines:
            for word in line.word_boxes:
                out += (" " + word.content)
            out = out.strip()
            if out != "":
                break
        if out != "":
            break
    return out


def cmd_show(docid):
    """
    Arguments: <doc_id>
    Show document information (but not its content, see 'dump').
    See 'search' for the document id.
    """
    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    print ("Type: {}".format(type(doc)))
    print ("Number of pages: {}".format(doc.nb_pages))
    for page in doc.pages:
        nb_lines = 0
        nb_words = 0
        for line in page.boxes:
            nb_lines += 1
            nb_words += len(line.word_boxes)
        print ("  page {}: {} lines, {} words".format(
            page.page_nb, nb_lines, nb_words
        ))
    print ("Labels: {}".format(", ".join([l.name for l in doc.labels])))
    print ("First line: {}".format(_get_first_line(doc)))


def cmd_search(*args):
    """
    Arguments: <keyword1> [<keyword2> [<keyword3> [...]]]
    List the documents containing the keywords. Syntax is the same
    than with the search field in Paperwork-gui.
    Example: 'label:contrat AND paperwork'
    """
    if len(args) <= 0:
        sys.stderr.write("paperwork-shell: Need keywords.\n")
        return

    dsearch = get_docsearch()

    if is_verbose():
        print ("Search: {}".format(" ".join(args)))

    docs = dsearch.find_documents(" ".join(args))
    for doc in docs:
        if not is_verbose():
            print (doc.docid)
        else:
            sys.stdout.write("{} ({} pages) ".format(doc.docid, doc.nb_pages))
            sys.stdout.write(", ".join([l.name for l in doc.labels]))
            sys.stdout.write("\n")


def cmd_switch_workdir(new_workdir):
    """
    Arguments: <new work directory path>
    Change current Paperwork's work directory.
    Does *not* update the index.
    You should run 'paperwork-shell rescan' after this command.
    """
    if not os.path.exists(new_workdir) or not os.path.isdir(new_workdir):
        sys.stderr.write("New work directory must be an existing directory.")
        return
    pconfig = config.PaperworkConfig()
    pconfig.read()
    pconfig.settings['workdir'].value = new_workdir
    pconfig.write()


COMMANDS = {
    'dump': cmd_dump,
    'import': cmd_import,
    'rescan': cmd_rescan,
    'search': cmd_search,
    'show': cmd_show,
    'switch_workdir': cmd_switch_workdir,
}
