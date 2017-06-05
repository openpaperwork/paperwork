import gc
import itertools
import json
import os
import sys

import gi
import pyocr

gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Poppler', '0.18')

from . import config
from . import docimport
from . import docsearch
from .labels import Label
from . import fs


FS = fs.GioFileSystem()


def is_verbose():
    return os.environ['PAPERWORK_SHELL_VERBOSE'] != ""


def is_interactive():
    return os.environ['PAPERWORK_INTERACTIVE'] != ""


def verbose(txt):
    if is_verbose():
        print (txt)


def reply(data):
    if "status" not in data:
        data['status'] = 'ok'
    print (json.dumps(
        data, indent=4,
        separators=(',', ': '),
        sort_keys=True
    ))


def get_docsearch():
    pconfig = config.PaperworkConfig()
    pconfig.read()

    verbose("Work directory: {}".format(pconfig.settings['workdir'].value))

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

    Possible JSON replies:
        --
        { "status": "ok", "docid": "xxxxx", "label": "yyyyy" }
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
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
    verbose("Label {} added on document {}".format(
        label_name, docid
    ))
    reply({
        "docid": docid,
        "label": label_name,
    })


def cmd_delete_doc(docid):
    """
    Arguments: <document_id>

    Delete a document.

    Possible JSON replies:
        --
        { "status": "ok", "docid": "xxxx" }
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
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
    verbose("Document {} deleted".format(docid))
    reply({
        'docid': docid
    })


def cmd_dump(docid, page_nb=None):
    """
    Arguments: <document id> [<page number>]

    Dump the content of the specified document.
    Beware, page numbers start from 1.
    See 'search' for the document ids.

    Replies with page content.
    Beware: This is the only command not replying in JSON format.
    """
    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    pages = doc.pages
    pages = [page for page in pages]
    if page_nb:
        page_nb = int(page_nb)
        pages = pages[page_nb - 1:page_nb]
    for page in pages:
        verbose("=== Page {} ===".format(page.page_nb + 1))
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
        raise Exception("Unknown page format: {}".format(page_format))

    return tuple(args) + (quality, page_format)


def cmd_export_all(*args):
    """
    Arguments:
        <output folder> [-- [--quality <0-100>] [--page_format <page_format>]]

    Export all documents as PDF files.

    Default quality is 50.
    Default page format is A4.

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "docids": [
                        ["xxx", "file:///tmp/xxx.pdf"],
                        ["yyy", "file:///tmp/yyy.pdf"],
                        ["zzz", "file:///tmp/zzz.pdf"]
                      ],
            "output_dir": "file:///tmp",
        }
    """
    (output_dir, quality, page_format) = _get_export_params(args)

    dsearch = get_docsearch()

    try:
        os.mkdir(output_dir)
    except FileExistsError:  # NOQA (Python 3.x only)
        pass

    out = []

    docs = [d for d in dsearch.docs]
    docs.sort(key=lambda doc: doc.docid)
    output_dir = FS.safe(output_dir)
    for (doc_idx, doc) in enumerate(docs):
        output_pdf = FS.join(output_dir, doc.docid + ".pdf")

        exporter = doc.build_exporter(file_format="pdf")
        if exporter.can_change_quality:
            exporter.set_quality(quality)
        if exporter.can_select_format:
            exporter.set_page_format(page_format)
        verbose(
            "[{}/{}] Exporting {} --> {} ...".format(
                doc_idx + 1, len(docs), doc.docid, output_pdf
            )
        )
        exporter.save(output_pdf)
        out.append((doc.docid, output_pdf))
        doc = None
        gc.collect()

    verbose("Done")
    reply({
        "docids": out,
        "output_dir": output_dir,
    })


def cmd_export_doc(*args):
    """
    Arguments:
        <document id> <output PDF file path>
        [-- [--quality <0-100>] [--page_format <page_format>]]

    Export one document as a PDF file.

    Default quality is 50.
    Default page format is A4.

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "docid": "xxxx",
            "output_file": "file:///tmp/xxxx.pdf",
            "quality": 50,
            "page_format": "A4",
        }
    """
    (docid, output_pdf, quality, page_format) = _get_export_params(args)

    dsearch = get_docsearch()
    doc = dsearch.get(docid)

    exporter = doc.build_exporter(file_format="pdf")
    if exporter.can_change_quality:
        exporter.set_quality(quality)
    if exporter.can_select_format:
        exporter.set_page_format(page_format)
    verbose("Exporting {} --> {} ...".format(docid, output_pdf))
    output_pdf = FS.safe(output_pdf)
    exporter.save(output_pdf)
    verbose("Done")
    r = {
        "docid": doc.docid,
        "output_file": output_pdf,
    }
    if exporter.can_change_quality:
        r['quality'] = quality
    if exporter.can_select_format:
        r['page_format'] = page_format
    reply(r)


def cmd_guess_labels(*args):
    """
    Arguments: <document id> [-- [--apply]]

    Guess the labels that should be set on the document.
    Example: paperwork-shell guess_labels -- 20161207_1144_00_8 --apply

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "docid": "xxxx",
            "current_labels": ["label_a", "label_b"],
            "guessed_labels": ["label_b", "label_c"],
            "applied": "yes",
        }
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

    verbose("Current labels: {}".format(
        ", ".join([label.name for label in doc.labels])
    ))

    guessed = dsearch.guess_labels(doc)

    verbose("Guessed labels: {}".format(
        ", ".join([label.name for label in guessed])
    ))

    r = {
        'docid': doc.docid,
        'current_labels': [label.name for label in doc.labels],
        'guessed_labels': [label.name for label in guessed],
        'applied': "yes" if apply_labels else "no",
    }

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
        verbose("Document {} updated".format(docid))
    elif apply_labels:
        verbose("Document {} unchanged".format(docid))
    reply(r)


def _get_importer(fileuris, doc):
    importers = docimport.get_possible_importers(fileuris, current_doc=doc)

    if len(importers) <= 0:
        raise Exception("Don't know how to import {}".format(fileuris))
    if len(importers) == 1:
        return importers[0]
    elif not is_interactive():
        raise Exception(
            "Many way to import {} and running in batch mode. Can't import.\n{}"
            .format(
                fileuris,
                ", ".join([str(importer) for importer in importers])
            )
        )
    else:
        verbose("Import of {}:")
        for (idx, importer) in enumerate(importers):
            verbose("{} - {}".format(idx, importer))
        idx = input("? ")
        return importers[int(idx)]


def _do_import(filepaths, dsearch, doc, ocr=None, ocr_lang=None,
               guess_labels=True):
    index_updater = dsearch.get_index_updater(optimize=False)

    fileuris = [FS.safe(f) for f in filepaths]

    for fileuri in fileuris:
        # safety checks first
        if not FS.exists(fileuri):
            raise FileNotFoundError(fileuri)  # NOQA (Python 3.x only)

    importer = _get_importer(fileuris, doc)
    verbose("Files {}: Importer = {}".format(fileuris, importer))
    import_result = importer.import_doc(
        fileuris, dsearch, current_doc=doc
    )

    verbose("{}:".format(fileuris))
    r = {
        "imports": import_result.get(),
        "ocr": [],
        "guessed_labels": [],
    }

    if ocr is not None:
        for page in itertools.chain(
            import_result.new_docs_pages,
            import_result.upd_docs_pages
        ):
            if len(page.boxes) > 0:
                verbose("Page {} has already some text. No OCR run".format(
                    page.pageid
                ))
                continue
            verbose("Running OCR on page {}".format(page.pageid))
            page.boxes = ocr.image_to_string(
                page.img,
                lang=ocr_lang,
                builder=pyocr.builders.LineBoxBuilder()
            )
            r['ocr'].append(page.pageid)

    for doc in import_result.new_docs:
        if guess_labels:
            labels = dsearch.guess_labels(doc)
            r['guessed_labels'].append(
                {
                    "docid": doc.docid,
                    "labels": [label.name for label in labels],
                }
            )
            for label in labels:
                dsearch.add_label(doc, label, update_index=False)
        verbose("Document {} (labels: {})".format(
            doc.docid,
            ", ".join([label.name for label in doc.labels])
        ))
        index_updater.add_doc(doc)

    for doc in import_result.upd_docs:
        verbose("Document {} (labels: {})".format(
            doc.docid,
            ", ".join([label.name for label in doc.labels])
        ))
        index_updater.upd_doc(doc)

    verbose("Updating index ...")
    index_updater.commit()
    verbose("Done")
    reply(r)


def cmd_import(*args):
    """
    Arguments:
        <file_or_folder> [<file_or_folder> [...]]
            [-- [--no_ocr] [--no_label_guessing] [--append <document_id>]]

    Import a file or a PDF folder. OCR is run by default on images
    and on PDF pages without text (PDF containing only images)

    Please keep in mind that documents that are already in the word directory
    are never imported again and are simply ignored.

    Example: paperwork-shell import -- somefile.pdf --no_label_guessing

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "ocr": [
                "20170602_1513_12|0",
                "20170602_1513_12|1"
            ],
            "imports": {
                # beware this section is filled in *before* label guessing
                "imported_file_uris": [
                    "file:///home/jflesch/tmp/pouet.pdf"
                ],
                "new_docs": [
                    {
                        "docid": "20170602_1513_12",
                        "labels": []
                    }
                ],
                "new_docs_pages": [
                    "20170602_1513_12|0",
                    "20170602_1513_12|1"
                ],
                "stats": {
                    # ~Human readable statistics
                    # exact content of this section is not guaranteed
                    "Document(s)": 1,
                    "Image file(s)": 0,
                    "PDF": 1,
                    "Page(s)": 2
                },
                "upd_docs": [],
                "upd_docs_pages": []
            }
            "guessed_labels": [
                {
                    "docid": "20170602_1513_12",
                    "labels": [
                        "Documentation"
                    ]
                }
            ]
        }
    """
    guess_labels = True
    ocr = pyocr.get_available_tools()
    docid = None
    doc = None

    args = list(args)

    if len(ocr) <= 0:
        raise Exception("No OCR tool found")
    ocr = ocr[0]

    if "--no_label_guessing" in args:
        guess_labels = False
        args.remove("--no_label_guessing")
    if "--no_ocr" in args:
        ocr = None
        args.remove("--no_ocr")
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

    ocr_lang = None
    if ocr is not None:
        pconfig = config.PaperworkConfig()
        pconfig.read()
        ocr_lang = pconfig.settings['ocr_lang'].value
    return _do_import(args, dsearch, doc, ocr, ocr_lang, guess_labels)


def cmd_ocr(*args):
    """
    Arguments:
        <document id or page id> [<document id or page id> [...]]
        [-- [--lang <ocr_lang>] [--empty_only]]

    Re-run the OCR on the specified elements. Elements can be whole documents
    or specific pages.

    --lang: specifies the language to use for OCR.
    The default language used is the one in Paperwork's configuration

    --empty_only: if set, only the pages with no text are run through the OCR.
    Otherwise, all pages are run through it.

    Examples:
        Documents:
          paperwork-shell ocr 20170512_1252_51 20170512_1241_40
          paperwork-shell ocr 20170512_1252_51 20170512_1241_40 -- --lang fra
        Pages:
          paperwork-shell ocr "20170512_1252_51|2" "20170512_1241_40|1"

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "ocr": [
                "20170602_1513_12|0",
                "20170602_1513_12|1"
            ]
        }
    """
    ocr_lang = None
    empty_only = False

    args = list(args)

    ocr = pyocr.get_available_tools()
    if len(ocr) <= 0:
        raise Exception("No OCR tool found")
    ocr = ocr[0]

    if "--lang" in args:
        idx = args.index("--lang")
        ocr_lang = args[idx + 1]
        args.pop(idx)
        args.pop(idx)

    if "--empty_only" in args:
        empty_only = True
        args.remove("--empty_only")

    if ocr_lang is None:
        pconfig = config.PaperworkConfig()
        pconfig.read()
        ocr_lang = pconfig.settings['ocr_lang'].value

    dsearch = get_docsearch()
    pages = set()
    docs = set()

    for objid in args:
        obj = dsearch.get(objid)
        if hasattr(obj, 'pages'):
            pages.update(obj.pages)
        else:
            pages.add(obj)

    index_updater = dsearch.get_index_updater(optimize=False)

    for page in set(pages):
        if empty_only and len(page.boxes) > 0:
            pages.remove(page)
            continue
        verbose("Running OCR on {} ...".format(page.pageid))
        page.boxes = ocr.image_to_string(
            page.img,
            lang=ocr_lang,
            builder=pyocr.builders.LineBoxBuilder()
        )
        docs.add(page.doc)

    verbose("Updating index ...")
    for doc in docs:
        index_updater.upd_doc(doc)
    index_updater.commit()
    verbose("Done")

    reply({
        "ocr": [page.pageid for page in pages]
    })

def cmd_remove_label(docid, label_name):
    """
    Arguments: <document_id> <label_name>

    Remove a label from a document.

    Note that if the document was the last one to use the label,
    the label may disappear entirely from Paperwork.

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "docid": "xxxx",
            "labels": ["aaa", "bbb", "ccc"],  # after deletion
        }
    """
    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    if doc is None:
        raise Exception(
            "Document {} not found. Cannot remove label from it".format(
                docid
            )
        )

    for clabel in dsearch.label_list:
        if clabel.name == label_name:
            label = clabel
    else:
        raise Exception("Unknown label {}".format(label_name))

    dsearch.remove_label(doc, label)
    verbose("Label {} removed from document {}".format(label_name, docid))
    reply({
        "docid": docid,
        "labels": [l.name for l in doc.labels],
    })


def cmd_rename(old_docid, new_docid):
    """
    Arguments: <current document_id> <new document_id>

    Change the ID of a document.

    Note that the document id are also their date.
    Using an ID that is not a date may have side effects
    (the main one being the document won't be sorted correctly).

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "old_docid": "xxxx",
            "new_docid": "yyyy",
        }
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

    verbose("Document {} renamed into {}".format(old_docid, new_docid))
    reply({
        "old_docid": old_docid,
        "new_docid": new_docid
    })


class RescanManager(object):
    def __init__(self):
        self.dsearch = get_docsearch()
        self.dexaminer = self.dsearch.get_doc_examiner()
        self.index_updater = self.dsearch.get_index_updater()
        self.reply = {
            "new_docs": [],
            "updated_docs": [],
            "deleted_docs": [],
        }

    def _on_new_doc(self, doc):
        self.index_updater.add_doc(doc)
        verbose("New document: {}".format(doc.docid))
        self.reply['new_docs'].append(doc.docid)

    def _on_upd_doc(self, doc):
        self.index_updater.upd_doc(doc)
        self.changes['upd'].add(doc)
        verbose("Updated document: {}".format(doc.docid))
        self.reply['updated_docs'].append(doc.docid)

    def _on_del_doc(self, doc):
        self.index_updater.del_doc(doc)
        verbose("Deleted document: {}".format(doc.docid))
        self.reply['deleted_docs'].append(doc.docid)

    def _on_doc_unchanged(self, doc):
        pass

    def _on_progress(self, progression, total, step=None, doc=None):
        if not is_verbose():
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
        if is_verbose():
            sys.stdout.write("\b" * 100 + " " * 100)
            sys.stdout.write("\b" * 100)
            verbose("Rewriting index ...")
        self.index_updater.commit()
        verbose("Done")


def cmd_rescan():
    """
    Rescan the work directory. Look for new, updated or deleted documents
    and update the index accordingly.

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "new_docs": ["xxx", "yyy"],
            "updated_docs": ["xxx", "yyy"],
            "deleted_docs": ["xxx", "yyy"],
        }
    """
    rm = RescanManager()
    rm.rescan()
    reply(rm.reply)


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

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "type": "ImgDoc",
            "nb_pages": 3,
            "pages": [
                {"n": 1, "lines": 10, "words": 22},
                {"n": 2, "lines": 20, "words": 22},
                {"n": 3, "lines": 30, "words": 34},
            ],
            "labels": ["aaa", "bbb"],
            "first_line": "vwklsd wldkwq",
        }
    """
    dsearch = get_docsearch()
    doc = dsearch.get(docid)
    r = {
        'type': str(type(doc)),
        'nb_pages': doc.nb_pages,
        'labels': [l.name for l in doc.labels],
        'first_line': _get_first_line(doc),
        'pages': []
    }
    for page in doc.pages:
        nb_lines = 0
        nb_words = 0
        for line in page.boxes:
            nb_lines += 1
            nb_words += len(line.word_boxes)
        r['pages'].append({
            "n": page.page_nb + 1,
            "lines": nb_lines,
            "words": nb_words,
        })
    reply(r)


def cmd_search(*args):
    """
    Arguments: <keyword1> [<keyword2> [<keyword3> [...]]]

    List the documents containing the keywords.

    Syntax is the same than with the search field in Paperwork-gui.
    Search "" (empty string) to get all the documents.

    Example: 'label:contrat AND paperwork'

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "results" [
                {"docid": "xxxx", "nb_pages": 22, "labels": ["xxx", "yyy"]}
                {"docid": "yyyy", "nb_pages": 22, "labels": ["xxx", "yyy"]}
                {"docid": "zzzz", "nb_pages": 22, "labels": ["xxx", "yyy"]}
            ],
        }
    """
    dsearch = get_docsearch()

    verbose("Search: {}".format(" ".join(args)))

    r = {'results': []}

    docs = dsearch.find_documents(" ".join(args))
    docs.sort(key=lambda doc: doc.docid)
    for doc in docs:
        r['results'].append({
            'docid': doc.docid,
            'nb_pages': doc.nb_pages,
            'labels': [l.name for l in doc.labels],
        })
    reply(r)


def cmd_switch_workdir(new_workdir):
    """
    Arguments: <new work directory path>

    Change current Paperwork's work directory.

    Does *not* update the index.
    You should run 'paperwork-shell rescan' after this command.

    Possible JSON replies:
        --
        {
            "status": "error", "exception": "yyy",
            "reason": "xxxx", "args": "(xxxx, )"
        }
        --
        {
            "status": "ok",
            "old_workdir": "file:///home/jflesch/papers",
            "new_workdir": "file:///tmp/papers",
        }
    """
    new_workdir = FS.safe(new_workdir)
    if not FS.exists(new_workdir) or not FS.isdir(new_workdir):
        sys.stderr.write("New work directory {} doesn't exists".format(
            new_workdir
        ))
        return
    pconfig = config.PaperworkConfig()
    pconfig.read()
    r = {
        'old_workdir': pconfig.settings['workdir'].value,
        'new_workdir': new_workdir
    }
    pconfig.settings['workdir'].value = new_workdir
    pconfig.write()
    reply(r)


COMMANDS = {
    'add_label': cmd_add_label,
    'delete_doc': cmd_delete_doc,
    'dump': cmd_dump,
    'export_all': cmd_export_all,
    'export_doc': cmd_export_doc,
    'guess_labels': cmd_guess_labels,
    'import': cmd_import,
    'ocr': cmd_ocr,
    'remove_label': cmd_remove_label,
    'rename': cmd_rename,
    'rescan': cmd_rescan,
    'search': cmd_search,
    'show': cmd_show,
    'switch_workdir': cmd_switch_workdir,
}
