#!/usr/bin/env python

import os
import sys

from setuptools import setup

setup(
    name="paperwork",
    # if you change the version, don't forget to
    # * update the ChangeLog file
    # * change it also in
    #   src/paperwork/frontend/aboutdialog/aboutdialog.glade
    # * update the archive list in the README
    version="0.3.2",
    description=(
        "Using scanner and OCR to grep dead trees the easy way (Linux only)"
    ),
    long_description="""Paperwork is a tool to make papers searchable.

The basic idea behind Paperwork is "scan & forget" : You should be able to
just scan a new document and forget about it until the day you need it
again.
Let the machine do most of the work.

Main features are:
- Scan
- Automatic orientation detection
- OCR
- Indexing
- Document labels
- Automatic guessing of the labels to apply on new documents
- Search
- Keyword suggestions
- Quick edit of scans
- PDF support
    """,
    keywords="scanner ocr gui",
    url="https://github.com/jflesch/paperwork",
    download_url=("https://github.com/jflesch/paperwork"
                  "/archive/unstable.tar.gz"),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: X11 Applications :: GTK",
        "Environment :: X11 Applications :: Gnome",
        "Intended Audience :: End Users/Desktop",
        ("License :: OSI Approved ::"
         " GNU General Public License v3 or later (GPLv3+)"),
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2.7",
        "Topic :: Multimedia :: Graphics :: Capture :: Scanners",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
        "Topic :: Scientific/Engineering :: Image Recognition",
        "Topic :: Text Processing :: Filters",
        "Topic :: Text Processing :: Indexing",
    ],
    license="GPLv3+",
    author="Jerome Flesch",
    author_email="jflesch@gmail.com",
    packages=[
        'paperwork',
        'paperwork.frontend',
        'paperwork.frontend.aboutdialog',
        'paperwork.frontend.import',
        'paperwork.frontend.labeleditor',
        'paperwork.frontend.mainwindow',
        'paperwork.frontend.multiscan',
        'paperwork.frontend.searchdialog',
        'paperwork.frontend.settingswindow',
        'paperwork.frontend.util',
        'paperwork.frontend.util.canvas',
        'paperwork.frontend.widgets',
        'paperwork.backend',
        'paperwork.backend.common',
        'paperwork.backend.pdf',
        'paperwork.backend.img',
    ],
    package_dir={
        'paperwork': 'src/paperwork',
        'paperwork.frontend': 'src/paperwork/frontend',
        'paperwork.frontend.aboutdialog':
        'src/paperwork/frontend/aboutdialog',
        'paperwork.frontend.import': 'src/paperwork/frontend/import',
        'paperwork.frontend.labeleditor':
        'src/paperwork/frontend/labeleditor',
        'paperwork.frontend.mainwindow': 'src/paperwork/frontend/mainwindow',
        'paperwork.frontend.multiscan': 'src/paperwork/frontend/multiscan',
        'paperwork.frontend.settingswindow':
        'src/paperwork/frontend/settingswindow',
        'paperwork.frontend.searchdialog':
        'src/paperwork/frontend/searchdialog',
        'paperwork.frontend.util': 'src/paperwork/frontend/util',
        'paperwork.frontend.util.canvas':
        'src/paperwork/frontend/util/canvas',
        'paperwork.frontend.widgets': 'src/paperwork/frontend/widgets',
        'paperwork.backend': 'src/paperwork/backend',
        'paperwork.backend.common': 'src/paperwork/backend/common',
        'paperwork.backend.pdf': 'src/paperwork/backend/pdf',
        'paperwork.backend.img': 'src/paperwork/backend/img',
    },
    data_files=[
        # css file
        (
            os.path.join(sys.prefix, 'share/paperwork'),
            [
                'src/paperwork/frontend/application.css',
            ]
        ),
        # glade files
        (
            os.path.join(sys.prefix, 'share/paperwork/aboutdialog'),
            [
                'src/paperwork/frontend/aboutdialog/aboutdialog.glade',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/searchdialog'),
            [
                'src/paperwork/frontend/searchdialog/searchdialog.glade',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/settingswindow'),
            [
                'src/paperwork/frontend/settingswindow/settingswindow.glade',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/import'),
            [
                'src/paperwork/frontend/import/importaction.glade',
                'src/paperwork/frontend/import/importfileselector.glade',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/labeleditor'),
            [
                'src/paperwork/frontend/labeleditor/labeleditor.glade',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/mainwindow'),
            [
                'src/paperwork/frontend/mainwindow/appmenu.xml',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/mainwindow'),
            [
                'src/paperwork/frontend/mainwindow/mainwindow.glade',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/multiscan'),
            [
                'src/paperwork/frontend/multiscan/multiscan.glade',
            ]
        ),
        (os.path.join(sys.prefix, 'share/locale/fr/LC_MESSAGES'),
         ['locale/fr/LC_MESSAGES/paperwork.mo']),
        (os.path.join(sys.prefix, 'share/locale/de/LC_MESSAGES'),
         ['locale/de/LC_MESSAGES/paperwork.mo']),
        (os.path.join(sys.prefix, 'share/applications'),
         ['data/paperwork.desktop']),
        (os.path.join(sys.prefix, 'share/icons'),
         ['data/paperwork.svg']),
    ],
    scripts=[
        'scripts/paperwork',
        'scripts/paperwork-chkdeps',
    ],
    install_requires=[
        "Pillow",
        "pycountry",
        "pyenchant",
        "python-Levenshtein",
        "pyinsane >= 1.3.8",
        "pyocr >= 0.3.0",
        "termcolor",  # used by paperwork-chkdeps
        "Whoosh",
        "simplebayes",
        # paperwork-chkdeps take care of all the dependencies that can't be
        # handled here. For instance:
        # - Dependencies using gobject introspection
        # - Dependencies based on language (OCR data files, dictionnaries, etc)
        # - Dependencies on data files (icons, etc)
    ]
)

print ("======================================================================")
print ("======================================================================")
print ("||                           IMPORTANT                              ||")
print ("||  Please run 'paperwork-chkdeps' to find any missing dependency   ||")
print ("======================================================================")
print ("======================================================================")
