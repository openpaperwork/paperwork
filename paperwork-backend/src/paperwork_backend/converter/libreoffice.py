import logging
import os
import subprocess
import tempfile

import openpaperwork_core
import paperwork_backend.deps

from .. import _


LOGGER = logging.getLogger(__name__)


LIBREOFFICE = [
    r'libreoffice',
    r'soffice',
    r'soffice.exe',
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'/app/libreoffice/program/soffice.bin',  # Flatpak
]

LIBREOFFICE_ARGS = [
    '--nocrashreport',
    '--nodefault',
    '--nofirststartwizard',
    '--nolockcheck',
    '--nologo',
    '--norestore',
    '--headless',
    '--convert-to', 'pdf',
    '--outdir', '{out_dir}',
    '{in_doc}',
]


def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


def which(program):
    if os.path.sep in program:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


class Plugin(openpaperwork_core.PluginBase):
    FILE_TYPES = [
        (
            "application/msword", "doc",
            "Microsoft Word (.doc)",
        ),
        (
            "application/msword", "dot",
            _("Microsoft Word template (.dot)"),
        ),
        (
            "application/vnd.ms-excel", "xls",
            "Microsoft Excel (.xls)",
        ),
        (
            "application/vnd.ms-excel", "xlt",
            _("Microsoft Excel template (.xlt)"),
        ),
        (
            "application/vnd.ms-powerpoint", "pps",
            "Microsoft PowerPoint (.pps)",
        ),
        (
            "application/vnd.ms-powerpoint", "ppt",
            _("Microsoft PowerPoint template (.ppt)"),
        ),
        (
            "application/vnd.oasis.opendocument.chart", "odc",
            _("OpenOffice/LibreOffice Chart (.odc)"),
        ),
        (
            "application/vnd.oasis.opendocument.database", "odb",
            _("OpenOffice/LibreOffice Database (.odb)"),
        ),
        (
            "application/vnd.oasis.opendocument.formula", "odf",
            _("OpenOffice/LibreOffice Formula (.odf)"),
        ),
        (
            "application/vnd.oasis.opendocument.graphics", "odg",
            _("OpenOffice/LibreOffice Graphics (.odg)"),
        ),
        (
            "application/vnd.oasis.opendocument.graphics-template", "otg",
            _("OpenOffice/LibreOffice Graphics template (.otg)"),
        ),
        (
            "application/vnd.oasis.opendocument.image", "odi",
            _("OpenOffice/LibreOffice Image template (.odi)"),
        ),
        (
            "application/vnd.oasis.opendocument.presentation", "odp",
            _("OpenOffice/LibreOffice Presentation (.odp)"),
        ),
        (
            "application/vnd.oasis.opendocument.presentation-template", "otp",
            _("OpenOffice/LibreOffice Presentation template (.otp)"),
        ),
        (
            "application/vnd.oasis.opendocument.spreadsheet", "ods",
            _("OpenOffice/LibreOffice Spreadsheet (.ods)"),
        ),
        (
            "application/vnd.oasis.opendocument.spreadsheet-template", "ots",
            _("OpenOffice/LibreOffice Spreadsheet template (.ots)"),
        ),
        (
            "application/vnd.oasis.opendocument.text", "odt",
            _("OpenOffice/LibreOffice Text (.odt)"),
        ),
        (
            "application/vnd.oasis.opendocument.text-master", "odm",
            _("OpenOffice/LibreOffice Text master (.odm)"),
        ),
        (
            "application/vnd.oasis.opendocument.text-template", "ott",
            _("OpenOffice/LibreOffice Text template (.ott)"),
        ),
        (
            "application/vnd.oasis.opendocument.text-web", "oth",
            _("OpenOffice/LibreOffice Text web (.oth)"),
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".presentation",
            "pptx",
            "Microsoft PowerPoint presentation (.pptx)",
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".slide",
            "sldx",
            _("Microsoft PowerPoint slide (.sldx)"),
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".slideshow",
            "ppsx",
            _("Microsoft PowerPoint slideshow (.ppsx)"),
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".template",
            "potx",
            _("Microsoft PowerPoint presentation template (.potx)"),
        ),
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml"
            ".sheet",
            "xlsx",
            "Microsoft Excel (.xlsx)",
        ),
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml"
            ".template",
            "xltx",
            _("Microsoft Excel template (.xltx)"),
        ),
        (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document",
            "docx",
            "Microsoft Word (.docx)",
        ),
        (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.template",
            "dotx",
            _("Microsoft Word template (.dotx)"),
        ),
    ]

    def __init__(self):
        self.libreoffice = None

    def get_interfaces(self):
        return [
            "chkdeps",
            "doc_converter",
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio']
            },
        ]

    def init(self, core):
        super().init(core)
        for exe in LIBREOFFICE:
            self.libreoffice = which(exe)
            if self.libreoffice is not None:
                break
        LOGGER.info("Libreoffice: %s", self.libreoffice)

    def chkdeps(self, out: dict):
        if self.libreoffice is None:
            out['libreoffice'] = paperwork_backend.deps.LIBREOFFICE

    def converter_get_file_types(self, out: list):
        if self.libreoffice is None:
            return
        out += self.FILE_TYPES

    def convert_file_to_pdf(self, doc_file_uri, mime_type, out_pdf_file_url):
        if self.libreoffice is None:
            return None

        for (mime, ext, desc) in self.FILE_TYPES:
            if mime_type == mime:
                break
        else:
            return None

        LOGGER.info(
            "Converting %s (%s) to %s (PDF)",
            doc_file_uri, mime_type, out_pdf_file_url
        )

        file_name = self.core.call_success("fs_basename", doc_file_uri)
        if "." not in file_name:
            LOGGER.error("No file extension ? %s", doc_file_uri)
            return None
        file_ext = file_name.rsplit(".", 1)[-1]

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            src_file = os.path.join(tmp_dir, "doc." + file_ext)
            dst_file = os.path.join(tmp_dir, "doc.pdf")

            # Assume Libreoffice only supports local files
            self.core.call_success(
                "fs_copy", doc_file_uri,
                self.core.call_success("fs_safe", src_file)
            )
            if not self.core.call_success(
                    "fs_exists", self.core.call_success("fs_safe", src_file)):
                LOGGER.error("Failed to copy file %s", doc_file_uri)
                return None

            os.chdir(tmp_dir)
            try:
                args = [
                    x.format(in_doc=src_file, out_dir=tmp_dir)
                    for x in LIBREOFFICE_ARGS
                ]
                popen = subprocess.Popen(
                    [self.libreoffice] + args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                with popen:
                    (stdout, stderr) = popen.communicate()

                dst_file_url = self.core.call_success("fs_safe", dst_file)

                if not self.core.call_success("fs_exists", dst_file_url):
                    LOGGER.error(
                        "Failed to convert %s (%s) to %s|%s (PDF)",
                        doc_file_uri, mime_type, dst_file_url, out_pdf_file_url
                    )
                    LOGGER.error("Command was: %s", [self.libreoffice] + args)
                    LOGGER.error("LibreOffice stdout: %s", stdout)
                    LOGGER.error("LibreOffice stderr: %s", stderr)
                    return False

                self.core.call_success(
                    "fs_copy",
                    dst_file_url,
                    out_pdf_file_url
                )
            finally:
                os.chdir(cwd)
        return True
