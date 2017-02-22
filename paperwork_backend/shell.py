import gc
from pprint import pprint
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
from .labels import Label


def is_verbose():
    return os.environ['PAPERWORK_SHELL_VERBOSE'] != ""


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


def cmd_add_label(docid, label_name, color=None):
    """
    Arguments: <document_id> <label_name> [<label_color>]
    Add a label on a document.
    Color must be specified if the label doesn't exist yet.
    Color will be ignored if the label already exists.
    Color format must be given in hexadecimal format. Ex: #abcdef
    """
    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    if doc is None:
        raise Exception(
            "Document {} not found. Cannot add label on it".format(
                docid
            )
        )

    label = None
    for clabel in dsearch.label_list:
        if clabel.name == label_name:
            label = clabel
            break
    if not label and not color:
        raise Exception(
            "Label {} doesn't exist yet, and no color has been provided".format(
                label_name
            )
        )
    if not label:
        label = Label(label_name, color)
        dsearch.create_label(label)

    dsearch.add_label(doc, label)
    print ("Label {} added on document {}".format(
        label_name, docid
    ))


def cmd_delete_doc(docid):
    """
    Arguments: <document_id>
    Delete a document.
    """
    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    if doc is None:
        raise Exception(
            "Document {} not found. Cannot delete it".format(
                docid
            )
        )
    index_updater = dsearch.get_index_updater(optimize=False)
    index_updater.del_doc(doc)
    index_updater.commit()
    doc.destroy()
    print ("Document {} deleted".format(docid))


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


def _get_export_params(args):
    from gi.repository import Gtk

    quality = 50
    page_format = "A4"

    args = list(args)

    if "--quality" in args:
        idx = args.index("--quality")
        quality = args[idx + 1]
        args.pop(idx)
        args.pop(idx)
        quality = int(quality)
    if "--page_format" in args:
        idx = args.index("--page_format")
        page_format = args[idx + 1]
        args.pop(idx)
        args.pop(idx)

    for paper_size in Gtk.PaperSize.get_paper_sizes(True):
        if (paper_size.get_display_name() == page_format or
                paper_size.get_name() == page_format):
            page_format = (
                paper_size.get_width(Gtk.Unit.POINTS),
                paper_size.get_height(Gtk.Unit.POINTS)
            )
            break

    if not isinstance(page_format, tuple):
        sys.stderr.write("Unknown page format: {}".format(page_format))
        return

    return tuple(args) + (quality, page_format)


def cmd_export_all(*args):
    """
    Arguments:
        <output folder> [-- [--quality <0-100>] [--page_format <page_format>]]
    Export all documents as PDF files.
    Default quality is 50.
    Default page format is A4.
    """
    (output_dir, quality, page_format) = _get_export_params(args)

    dsearch = get_docsearch()

    try:
        os.mkdir(output_dir)
    except FileExistsError:
        pass

    docs = [d for d in dsearch.docs]
    docs.sort(key=lambda doc: doc.docid)
    for (doc_idx, doc) in enumerate(docs):
        output_pdf = os.path.join(output_dir, doc.docid + ".pdf")

        exporter = doc.build_exporter(file_format="pdf")
        if exporter.can_change_quality:
            exporter.set_quality(quality)
        if exporter.can_select_format:
            exporter.set_page_format(page_format)
        print (
            "[{}/{}] Exporting {} --> {} ...".format(
            doc_idx + 1, len(docs), doc.docid, output_pdf)
        )
        exporter.save(output_pdf)
        doc.drop_cache()
        gc.collect()

    print ("Done")


def cmd_export_doc(*args):
    """
    Arguments:
        <document id> <output PDF file path>
        [-- [--quality <0-100>] [--page_format <page_format>]]
    Export one document as a PDF file.
    Default quality is 50.
    Default page format is A4.
    """
    (docid, output_pdf, quality, page_format) = _get_export_params(args)

    dsearch = get_docsearch()
    doc = dsearch.get(docid)

    exporter = doc.build_exporter(file_format="pdf")
    if exporter.can_change_quality:
        exporter.set_quality(quality)
    if exporter.can_select_format:
        exporter.set_page_format(page_format)
    print ("Exporting {} --> {} ...".format(docid, output_pdf))
    exporter.save(output_pdf)
    print ("Done")


def cmd_guess_labels(*args):
    """
    Arguments: <document id> [-- [--apply]]
    Guess the labels that should be set on the document.
    Example: paperwork-shell -v guess_labels -- 20161207_1144_00_8 --apply
    """
    args = list(args)

    apply_labels = False
    if "--apply" in args:
        apply_labels = True
        args.remove("--apply")
    docid = args[0]

    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    if doc is None:
        raise Exception(
            "Document {} not found. Cannot guess labels".format(
                docid
            )
        )

    print ("Current labels: {}".format(
        ", ".join([label.name for label in doc.labels])
    ))

    guessed = dsearch.guess_labels(doc)

    print ("Guessed labels: {}".format(
        ", ".join([label.name for label in guessed])
    ))

    changed = False
    if apply_labels:
        for label in guessed:
            if label not in doc.labels:
                dsearch.add_label(doc, label, update_index=False)
                changed = True
        for label in doc.labels:
            if label not in guessed:
                dsearch.remove_label(doc, label, update_index=False)
                changed = True

    if changed:
        index_updater = dsearch.get_index_updater(optimize=False)
        index_updater.upd_doc(doc)
        index_updater.commit()
        print ("Document {} updated".format(docid))
    elif apply_labels:
        print ("Document {} unchanged".format(docid))


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
        import_result = importer.import_doc(
            fileuri, dsearch, current_doc=doc
        )

        print("{}:".format(filepath))
        pprint(import_result.stats)

        for doc in import_result.new_docs:
            if guess_labels:
                labels = dsearch.guess_labels(doc)
                for label in labels:
                    dsearch.add_label(doc, label, update_index=False)
            if is_verbose():
                print("{} --> Document {} (labels: {})".format(
                    filepath, doc.docid,
                    ", ".join([label.name for label in doc.labels])
                ))
            index_updater.add_doc(doc)

        for doc in import_result.upd_docs:
            if is_verbose():
                print("{} --> Document {} (labels: {})".format(
                    filepath, doc.docid,
                    ", ".join([label.name for label in doc.labels])
                ))
            index_updater.upd_doc(doc)

    if is_verbose():
        print ("Updating index ...")
    index_updater.commit()
    if is_verbose():
        print ("Done")


def cmd_import(*args):
    """
    Arguments:
        <file_or_folder> [-- [--no_label_guessing] [--append <document_id>]]
    Import a file or a PDF folder.
    Example: paperwork-shell -v import -- somefile.pdf --no_label_guessing
    """
    guess_labels = True
    docid = None
    doc = None

    args = list(args)

    if "--no_label_guessing" in args:
        guess_labels = False
        args.remove("--no_label_guessing")
    if "--append" in args:
        idx = args.index("--append")
        docid = args[idx + 1]
        args.pop(idx)
        args.pop(idx)
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


def cmd_remove_label(docid, label_name):
    """
    Arguments: <document_id> <label_name>
    Remove a label from a document.
    Note that if the document was the last one to use the label,
    the label may disappear entirely from Paperwork.
    """
    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    if doc is None:
        raise Exception(
            "Document {} not found. Cannot remove label from it".format(
                docid
            )
        )

    label = None
    for clabel in dsearch.label_list:
        if clabel.name == label_name:
            label = clabel
            break
    if label is None:
        raise Exception("Unknown label {}".format(label_name))

    dsearch.remove_label(doc, label)
    print ("Label {} removed from document {}".format(label_name, docid))


def cmd_rename(old_docid, new_docid):
    """
    Arguments: <current document_id> <new document_id>
    Change the ID of a document.
    Note that the document id are also their date.
    Using an ID that is not a date may have side effects
    (the main one being the document won't be sorted correctly).
    """
    dsearch = get_docsearch()
    doc = dsearch.get(old_docid)
    if doc is None:
        raise Exception(
            "Document {} not found. Cannot remove label from it".format(
                old_docid
            )
        )

    index_updater = dsearch.get_index_updater(optimize=False)

    # just clone the in-memory data, not the on-disk content
    clone = doc.clone()

    # so we can change the ID safely
    doc.docid = new_docid

    index_updater.del_doc(clone)
    index_updater.add_doc(doc)
    index_updater.commit()

    print ("Document {} renamed into {}".format(old_docid, new_docid))


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
    dsearch = get_docsearch()

    if is_verbose():
        print ("Search: {}".format(" ".join(args)))

    docs = dsearch.find_documents(" ".join(args))
    docs.sort(key=lambda doc: doc.docid)
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
    'add_label': cmd_add_label,
    'delete_doc': cmd_delete_doc,
    'dump': cmd_dump,
    'export_all': cmd_export_all,
    'export_doc': cmd_export_doc,
    'guess_labels': cmd_guess_labels,
    'import': cmd_import,
    'remove_label': cmd_remove_label,
    'rename': cmd_rename,
    'rescan': cmd_rescan,
    'search': cmd_search,
    'show': cmd_show,
    'switch_workdir': cmd_switch_workdir,
}
