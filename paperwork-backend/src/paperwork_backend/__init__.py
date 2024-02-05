import gettext

import openpaperwork_core
import openpaperwork_gtk


def _(s):
    return gettext.dgettext('paperwork_backend', s)


DEFAULT_CONFIG_PLUGINS = openpaperwork_core.MINIMUM_CONFIG_PLUGINS + [
    'paperwork_backend.app',
]

DEFAULT_PLUGINS = (
    openpaperwork_core.RECOMMENDED_PLUGINS +
    openpaperwork_gtk.CLI_PLUGINS +
    [
        'openpaperwork_core.beacon.stats',
        'openpaperwork_core.beacon.sysinfo',
        'openpaperwork_core.bug_report.censor',
        'openpaperwork_core.censor',
        'openpaperwork_core.pillow.img',
        'openpaperwork_core.pillow.util',
        'paperwork_backend.authors',
        'paperwork_backend.authors.translators',
        'paperwork_backend.beacon.update',
        'paperwork_backend.cairo.blur',
        'paperwork_backend.cairo.cache',
        'paperwork_backend.cairo.pillow',
        'paperwork_backend.cairo.poppler',
        'paperwork_backend.chkworkdir.corrupted_page_map',
        'paperwork_backend.chkworkdir.empty_doc',
        'paperwork_backend.chkworkdir.file_at_workdir_root',
        'paperwork_backend.chkworkdir.label_color',
        'paperwork_backend.converter.libreoffice',
        'paperwork_backend.datadirhandler',
        'paperwork_backend.docexport.automatic',
        'paperwork_backend.docexport.generic',
        'paperwork_backend.docexport.img',
        'paperwork_backend.docexport.pdf',
        'paperwork_backend.docexport.pillowfight',
        'paperwork_backend.docimport.converted',
        'paperwork_backend.docimport.img',
        'paperwork_backend.docimport.pdf',
        'paperwork_backend.docscan.libinsane',
        'paperwork_backend.docscan.scan2doc',
        'paperwork_backend.doctracker',
        # ACE is disabled by default: it's slow, and actually makes some scans
        # harder to read.
        # 'paperwork_backend.guesswork.color.libpillowfight',
        'paperwork_backend.guesswork.label.sklearn',
        'paperwork_backend.guesswork.ocr.pyocr',
        'paperwork_backend.guesswork.orientation.pyocr',
        'paperwork_backend.i18n.pycountry',
        'paperwork_backend.i18n.scanner',
        'paperwork_backend.imgedit.color',
        'paperwork_backend.imgedit.crop',
        'paperwork_backend.imgedit.rotate',
        'paperwork_backend.index.whoosh',
        'paperwork_backend.l10n',
        'paperwork_backend.model',
        'paperwork_backend.model.converted',
        'paperwork_backend.model.extra_text',
        'paperwork_backend.model.hocr',
        'paperwork_backend.model.img',
        'paperwork_backend.model.img_overlay',
        'paperwork_backend.model.labels',
        'paperwork_backend.model.pdf',
        'paperwork_backend.model.thumbnail',
        'paperwork_backend.model.workdir',
        'paperwork_backend.pageedit.pageeditor',
        'paperwork_backend.pagetracker',
        'paperwork_backend.pillow.pdf',
        'paperwork_backend.poppler.file',
        'paperwork_backend.poppler.memory',
        'paperwork_backend.pyocr',
        'paperwork_backend.sync',
    ]
)
