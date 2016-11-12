#!/usr/bin/env python3

import locale
import os
import sys

try:
    # suppress warnings from GI
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Poppler', '0.18')
    gi.require_version('PangoCairo', '1.0')
except:
    pass

try:
    from gi.repository import GLib
    from gi.repository import Gtk
    g_gtk_available = True
except Exception as exc:
    g_gtk_available = False


"""
Some modules/libraries required by Paperwork cannot be installed with pip or
easy_install. So we will just help the user detecting what is missing and what
must be installed
"""

LANGUAGES = {
    None: {
        'aspell': 'en',
        'tesseract': 'eng',
    },
    'fr': {
        'aspell': 'fr',
        'tesseract': 'fra',
    },
    'de': {
        'aspell': 'de',
        'tesseract': 'deu',
    },
    'en': {
        'aspell': 'en',
        'tesseract': 'eng',
    },
}

DEFAULT_LANG = {
    'aspell': '<your language>',
    'tesseract': '<your language>',
}

MODULES = [
    (
        'Gtk', 'gi.repository.Gtk',
        {
            'debian': 'gir1.2-gtk-3.0',
            'fedora': 'gtk3',
            'gentoo': 'x11-libs/gtk+',
            'linuxmint': 'gir1.2-gtk-3.0',
            'ubuntu': 'gir1.2-gtk-3.0',
            'suse': 'python-gtk',
        },
    ),
]

DATA_FILES = [
    (
        "Gnome symbolic icons"
        " (/usr/share/icons/gnome/(...)/go-previous-symbolic.svg",
        [
            "/usr/share/icons/gnome/scalable/actions/go-previous-symbolic.svg",
            "/usr/local/share/icons/gnome/scalable/"
            "actions/go-previous-symbolic.svg",
        ],
        {
            'debian': 'gnome-icon-theme-symbolic',
            'ubuntu': 'gnome-icon-theme-symbolic',
            'fedora': 'gnome-icon-theme-symbolic',
        }
    ),
]


def get_language():
    lang = locale.getdefaultlocale()[0]
    if lang:
        lang = lang[:2]
    if lang in LANGUAGES:
        return LANGUAGES[lang]
    print(
        "[WARNING] Unable to figure out the exact language package to install"
    )
    return DEFAULT_LANG


def find_missing_modules():
    """
    look for dependency that setuptools cannot check or that are too painful to
    install with setuptools
    """
    missing_modules = []

    for module in MODULES:
        try:
            __import__(module[1])
        except ImportError:
            missing_modules.append(module)
    return missing_modules


def find_missing_ocr(lang):
    """
    OCR tools are a little bit more tricky
    """
    missing = []
    try:
        from pyocr import pyocr
        ocr_tools = pyocr.get_available_tools()
    except ImportError:
        print (
            "[WARNING] Couldn't import Pyocr. Will assume OCR tool is not"
            " installed yet"
        )
        ocr_tools = []
    if len(ocr_tools) > 0:
        langs = ocr_tools[0].get_available_languages()
    else:
        langs = []
        missing.append(
            (
                'Tesseract', '(none)',
                {
                    'debian': 'tesseract-ocr',
                    'fedora': 'tesseract',
                    'gentoo': 'app-text/tesseract',
                    'linuxmint': 'tesseract-ocr',
                    'ubuntu': 'tesseract-ocr',
                },
            )
        )

    if (len(langs) <= 0 or lang['tesseract'] not in langs):
        missing.append(
            (
                'Tesseract language data', '(none)',
                {
                    'debian': ('tesseract-ocr-%s' % lang['tesseract']),
                    'fedora': ('tesseract-langpack-%s' % lang['tesseract']),
                    'linuxmint': ('tesseract-ocr-%s' % lang['tesseract']),
                    'ubuntu': ('tesseract-ocr-%s' % lang['tesseract']),
                },
            )
        )

    return missing


def find_missing_dict(lang):
    if os.name == "nt":
        return []
    import enchant
    missing = []
    try:
        enchant.request_dict(lang['aspell'])
    except:
        missing.append(
            (
                'Dictionary', '(none)',
                {
                    'debian': ('aspell-%s' % lang['aspell']),
                    'fedora': ('aspell-%s' % lang['aspell']),
                    'gentoo': ('aspell-%s' % lang['aspell']),
                    'linuxmint': ('aspell-%s' % lang['aspell']),
                    'ubuntu': ('aspell-%s' % lang['aspell']),
                }
            )
        )
    return missing


def _check_cairo():
    from gi.repository import Gtk

    class CheckCairo(object):
        def __init__(self):
            self.test_successful = False

        def on_draw(self, widget, cairo_ctx):
            self.test_successful = True
            Gtk.main_quit()
            return False

        def quit(self):
            try:
                Gtk.main_quit()
            except Exception as exc:
                print("FAILED TO STOP GTK !")
                print("ASSUMING python-gi-cairo is not installed")
                print("Exception was: {}".format(exc))
                sys.exit(1)

    check = CheckCairo()

    try:
        from gi.repository import GLib

        window = Gtk.Window()
        da = Gtk.DrawingArea()
        da.set_size_request(200, 200)
        da.connect("draw", check.on_draw)
        window.add(da)
        da.queue_draw()

        window.show_all()

        GLib.timeout_add(2000, check.quit)
        Gtk.main()
        window.set_visible(False)
        while Gtk.events_pending():
            Gtk.main_iteration()
    except Exception as exc:
        pass

    return check.test_successful


def check_cairo():
    missing = []
    if not g_gtk_available:
        success = False
    else:
        success = _check_cairo()
    if not success:
        missing.append(
            (
                'python-gi-cairo', '(none)',
                {
                    'debian': 'python3-gi-cairo',
                    'linuxmint': 'python3-gi-cairo',
                    'ubuntu': 'python3-gi-cairo',
                },
            )
        )

    return missing


def find_missing_data_files():
    missings = []
    for (user_name, file_paths, packages) in DATA_FILES:
        missing = True
        for file_path in file_paths:
            if os.path.exists(file_path):
                missing = False
                break
        if missing:
            missings.append((user_name, "(none)", packages))
    return missings


def find_missing_dependencies():
    lang = get_language()

    # missing_modules is an array of
    # (common_name, python_name, { "distrib": "package" })
    missing = []
    missing += find_missing_modules()
    missing += find_missing_ocr(lang)
    missing += find_missing_dict(lang)
    missing += find_missing_data_files()
    missing += check_cairo()
    # TODO(Jflesch): check for sane ?
    return missing
