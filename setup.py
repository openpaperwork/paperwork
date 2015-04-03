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
    version="0.2.3",
    description="Grep for dead trees",
    long_description="""
    Paperwork is a tool to make papers searchable.

    The basic idea behind Paperwork is "scan & forget" : You should be able to
    just scan a new document and forget about it until the day you need it
    again.
    Let the machine do most of the work.
    """,
    keywords="scanner ocr gui",
    url="https://github.com/jflesch/paperwork",
    download_url=("https://github.com/jflesch/paperwork"
                  "/archive/unstable.tar.gz"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: End Users/Desktop",
        ("License :: OSI Approved ::"
         " GNU General Public License v3 or later (GPLv3+)"),
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2.7",
        "Topic :: Multimedia :: Graphics :: Capture :: Scanners",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
        "Topic :: Scientific/Engineering :: Image Recognition",
        "Topic :: Text Processing :: Indexing",
    ],
    license="GPLv3+",
    author="Jerome Flesch",
    author_email="jflesch@gmail.com",
    packages=[
        'paperwork',
        'paperwork.frontend',
        'paperwork.frontend.aboutdialog',
        'paperwork.frontend.doceditdialog',
        'paperwork.frontend.import',
        'paperwork.frontend.labeleditor',
        'paperwork.frontend.mainwindow',
        'paperwork.frontend.multiscan',
        'paperwork.frontend.pageeditor',
        'paperwork.frontend.settingswindow',
        'paperwork.frontend.util',
        'paperwork.frontend.util.canvas',
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
        'paperwork.frontend.doceditdialog':
        'src/paperwork/frontend/doceditdialog',
        'paperwork.frontend.import': 'src/paperwork/frontend/import',
        'paperwork.frontend.labeleditor':
        'src/paperwork/frontend/labeleditor',
        'paperwork.frontend.mainwindow': 'src/paperwork/frontend/mainwindow',
        'paperwork.frontend.multiscan': 'src/paperwork/frontend/multiscan',
        'paperwork.frontend.pageeditor': 'src/paperwork/frontend/pageeditor',
        'paperwork.frontend.settingswindow':
        'src/paperwork/frontend/settingswindow',
        'paperwork.frontend.util': 'src/paperwork/frontend/util',
        'paperwork.frontend.util.canvas':
        'src/paperwork/frontend/util/canvas',
        'paperwork.backend': 'src/paperwork/backend',
        'paperwork.backend.common': 'src/paperwork/backend/common',
        'paperwork.backend.pdf': 'src/paperwork/backend/pdf',
        'paperwork.backend.img': 'src/paperwork/backend/img',
    },
    data_files=[
        # glade files
        (
            os.path.join(sys.prefix, 'share/paperwork/aboutdialog'),
            [
                'src/paperwork/frontend/aboutdialog/aboutdialog.glade',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/settingswindow'),
            [
                'src/paperwork/frontend/settingswindow/settingswindow.glade',
            ]
        ),
        (
            os.path.join(sys.prefix, 'share/paperwork/doceditdialog'),
            [
                'src/paperwork/frontend/doceditdialog/doceditdialog.glade',
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
        (
            os.path.join(sys.prefix, 'share/paperwork/pageeditor'),
            [
                'src/paperwork/frontend/pageeditor/pageeditor.glade',
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
        "Cython",
        'joblib',
        "Pillow",
        "pycountry",
        # "pycairo",  # doesn't work ?
        "pyenchant",
        "python-Levenshtein",
        "pyinsane >= 1.3.8",
        "pyocr >= 0.3.0",
        "numpy",
        "scipy",
        "scikit-learn",
        "scikit-image",
        "termcolor",  # used by paperwork-chkdeps
        "Whoosh",
        # "PyGObject",  # doesn't work with virtualenv
        # Missing due to the use of gobject introspection:
        # - gtk
        # - glade
        # - poppler
        # Missing because non-python libraries:
        # - sane
        # - tesseract/cuneiform
    ],
    )

print ("======================================================================")
print ("======================================================================")
print ("||                           IMPORTANT                              ||")
print ("||  Please run 'paperwork-chkdeps' to find any missing dependency   ||")
print ("======================================================================")
print ("======================================================================")
