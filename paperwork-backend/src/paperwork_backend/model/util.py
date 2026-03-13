import logging

from openpaperwork_core.interfaces.fs import Fs
import openpaperwork_core

from paperwork_backend.interfaces.docs import Docs


LOGGER = logging.getLogger(__name__)


def get_deps():
    return [
        openpaperwork_core.Dependency(
            interface=Fs,
            defaults=["openpaperwork_core.fs.python"],
        ),
        openpaperwork_core.Dependency(
            interface=Docs,
            defaults=["paperwork_backend.model"],
            optional=True,
        ),
    ]


def _shift_pages(core, page_filename_fmt, doc_url, start_page_idx, offset):
    assert offset != 0

    total_pages = core.call_success(Docs.doc_get_nb_pages_by_url, doc_url)
    if total_pages is None:
        total_pages = 0

    if offset < 0:
        rng = range(start_page_idx + 1, total_pages + 1)
    elif offset > 0:
        rng = range(total_pages - 1, start_page_idx - 1, -1)

    for page_idx in rng:
        old_url = core.call_success(
            Fs.fs_join, doc_url, page_filename_fmt.format(page_idx + 1)
        )
        if core.call_success(Fs.fs_exists, old_url) is None:
            continue
        new_url = core.call_success(
            Fs.fs_join, doc_url, page_filename_fmt.format(
                page_idx + 1 + offset
            )
        )
        LOGGER.info("  - %s --> %s", old_url, new_url)
        core.call_success(Fs.fs_rename, old_url, new_url)


def delete_page_file(core, page_filename_fmt, doc_url, page_idx, trash=True):
    file_url = core.call_success(
        Fs.fs_join, doc_url, page_filename_fmt.format(page_idx + 1)
    )
    if core.call_success(Fs.fs_exists, file_url) is not None:
        LOGGER.info(
            "(%s) Deleting %s p%d:", page_filename_fmt, doc_url, page_idx
        )
        core.call_success(Fs.fs_unlink, file_url, trash=trash)

    # move all the other pages 1 level down
    _shift_pages(core, page_filename_fmt, doc_url, page_idx, -1)
    return True


def move_page_file(
            core, page_filename_fmt,
            source_doc_url, source_page_idx,
            dest_doc_url, dest_page_idx
        ):
    if core.call_success(Fs.fs_exists, dest_doc_url) is None:
        assert dest_page_idx == 0
        core.call_success(Fs.fs_mkdir_p, dest_doc_url)

    LOGGER.info(
        "(%s) Move %s p%d --> %s p%d:", page_filename_fmt,
        source_doc_url, source_page_idx,
        dest_doc_url, dest_page_idx
    )

    # source_doc_url and dest_doc_url can be the same document, making
    # this change a little bit tricky. The simplest way to handle all the cases
    # is to:
    # --> move the page out of the source document (we rename it temporarily
    # page_filename_fmt.format(0))
    # --> then to insert it in the destination document

    # Move the page out of the source document
    src = core.call_success(
        Fs.fs_join, source_doc_url,
        page_filename_fmt.format(source_page_idx + 1)
    )
    dst = core.call_success(
        Fs.fs_join, dest_doc_url, page_filename_fmt.format(0)
    )
    if core.call_success(Fs.fs_exists, src) is not None:
        LOGGER.info("  - %s --> %s", src, dst)
        core.call_success(Fs.fs_rename, src, dst)

    _shift_pages(core, page_filename_fmt, source_doc_url, source_page_idx, -1)

    # Move the page in the destination document
    src = dst
    dst = core.call_success(
        Fs.fs_join, dest_doc_url, page_filename_fmt.format(dest_page_idx + 1)
    )
    _shift_pages(core, page_filename_fmt, dest_doc_url, dest_page_idx, 1)

    if core.call_success(Fs.fs_exists, src) is not None:
        LOGGER.info("  - %s --> %s", src, dst)
        core.call_success(Fs.fs_rename, src, dst)
    return True


def get_nb_pages(core, doc_url, filename_regex):
    if core.call_success(Fs.fs_exists, doc_url) is None:
        return None
    if core.call_success(Fs.fs_isdir, doc_url) is None:
        return None
    files = core.call_success(Fs.fs_listdir, doc_url)
    if files is None:
        return None
    nb_pages = -1
    for f in files:
        f = core.call_success(Fs.fs_basename, f)
        match = filename_regex.match(f)
        if match is None:
            continue
        nb_pages = max(nb_pages, int(match.group(1)))
    if nb_pages <= 0:
        return None
    return nb_pages


def get_page_hash(core, doc_url, page_idx, filename_fmt):
    page_url = core.call_success(
        Fs.fs_join, doc_url, filename_fmt.format(page_idx + 1)
    )
    if core.call_success(Fs.fs_exists, page_url) is None:
        return None
    return core.call_success(Fs.fs_hash, page_url)


def get_page_mtime(core, doc_url, page_idx, filename_fmt):
    page_url = core.call_success(
        Fs.fs_join, doc_url, filename_fmt.format(page_idx + 1)
    )
    if core.call_success(Fs.fs_exists, page_url) is None:
        return
    return core.call_success(Fs.fs_get_mtime, page_url)


def get_doc_mtime(core, doc_url, filename_regex):
    r = -1
    if core.call_success(Fs.fs_exists, doc_url) is None:
        return
    if core.call_success(Fs.fs_isdir, doc_url) is None:
        return
    files = core.call_success(Fs.fs_listdir, doc_url)
    if files is None:
        return None
    for f in files:
        f = core.call_success(Fs.fs_basename, f)
        match = filename_regex.match(f)
        if match is None:
            continue
        page_url = core.call_success(Fs.fs_join, doc_url, f)
        r = max(r, core.call_success(Fs.fs_get_mtime, page_url))
    if r < 0:
        return None
    return r
