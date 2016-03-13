#!/usr/bin/env python

from setuptools import setup

setup(
    name="paperwork",
    # if you change the version, don't forget to
    # * update the ChangeLog file
    # * change it also in
    #   data/paperwork/aboutdialog/aboutdialog.glade
    # * update the archive list in the README
    version="0.3.1.1-git",
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
            'share/paperwork',
            [
                'data/paperwork/application.css',
            ]
        ),
        # glade files
        (
            'share/paperwork/aboutdialog',
            [
                'data/paperwork/aboutdialog/aboutdialog.glade',
                'data/icons/paperwork.svg',
            ]
        ),
        (
            'share/paperwork/searchdialog',
            [
                'data/paperwork/searchdialog/searchdialog.glade',
            ]
        ),
        (
            'share/paperwork/settingswindow',
            [
                'data/paperwork/settingswindow/settingswindow.glade',
            ]
        ),
        (
            'share/paperwork/import',
            [
                'data/paperwork/import/importaction.glade',
                'data/paperwork/import/importfileselector.glade',
            ]
        ),
        (
            'share/paperwork/labeleditor',
            [
                'data/paperwork/labeleditor/labeleditor.glade',
            ]
        ),
        (
            'share/paperwork/mainwindow',
            [
                'data/paperwork/mainwindow/appmenu.xml',
                'data/paperwork/mainwindow/mainwindow.glade',
                'data/icons/paperwork.svg',
            ]
        ),
        (
            'share/paperwork/multiscan',
            [
                'data/paperwork/multiscan/multiscan.glade',
            ]
        ),
        ('share/locale/fr/LC_MESSAGES',
         ['data/locale/fr/LC_MESSAGES/paperwork.mo']),
        ('share/locale/de/LC_MESSAGES',
         ['data/locale/de/LC_MESSAGES/paperwork.mo']),
        ('share/applications',
         ['data/applications/paperwork.desktop']),
        ('share/icons',
         ['data/icons/paperwork.svg']),
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
