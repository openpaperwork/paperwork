#!/usr/bin/env python

import glob
import os

from setuptools import setup, find_packages

extra_deps = []

if os.name == "nt":
    extra_deps = [
        "pycrypto"  # used to check the activation keys
    ]

data_files = []

# include icons
for icon_dirpath in glob.glob('data/[0-9][0-9]*'):
    icon_path = os.path.join(icon_dirpath, 'paperwork.png')
    if os.path.exists(icon_path):
        size = os.path.basename(icon_dirpath)
        data_files.append(
            ('paperwork/frontend/share/icons/hicolor/{}/apps'.format(size),
             [icon_path])
        )

# include locales
for locale_dir in glob.glob("locale/??"):
    mo_dir = os.path.join(locale_dir, "LC_MESSAGES")
    mo = os.path.join(mo_dir, "paperwork.mo")
    data_files.append(
        (
            os.path.join('paperwork', 'frontend', 'share', mo_dir),
            [mo]
        ),
    )

setup(
    name="paperwork",
    # if you change the version, don't forget to
    # * update the download_url in this file
    # * update the ChangeLog file
    # * update AUTHORS
    # * change it also in
    #   src/paperwork/frontend/aboutdialog/aboutdialog.glade
    # * change it also in
    #   src/paperwork/frontend/mainwindow/__init__.py:__version__
    # * update the dependency version on paperwork-backend
    # * update the public key in
    #   src/paperwork/frontend/activation/__init__.py:check_activation_key()
    #   if required
    version="1.2",
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
                  "/archive/1.2.tar.gz"),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: X11 Applications :: GTK",
        "Environment :: X11 Applications :: Gnome",
        "Intended Audience :: End Users/Desktop",
        ("License :: OSI Approved ::"
         " GNU General Public License v3 or later (GPLv3+)"),
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Graphics :: Capture :: Scanners",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
        "Topic :: Scientific/Engineering :: Image Recognition",
        "Topic :: Text Processing :: Filters",
        "Topic :: Text Processing :: Indexing",
    ],
    license="GPLv3+",
    author="Jerome Flesch",
    author_email="jflesch@openpaper.work",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    data_files=[
        ('paperwork/frontend/share/icons/hicolor/scalable/apps',
         ['data/paperwork.svg', 'data/paperwork_halo.svg']),

        ('paperwork/frontend/mainwindow',
         ['data/paperwork_halo.svg']),
        ('paperwork/frontend/aboutdialog',
         ['data/paperwork.svg']),

        # documentation
        ('paperwork/frontend/doc', glob.glob('doc/*.pdf')),
    ] + data_files,
    entry_points={
        'gui_scripts': [
            'paperwork = paperwork.paperwork:main',
        ]
    },
    install_requires=[
        "python-dateutil",
        "python-Levenshtein",
        "Pillow",
        "pycountry",
        "pyinsane2",
        "pyocr >= 0.3.0",
        "pypillowfight",
        "pyxdg >= 0.25",
        "termcolor",  # used by paperwork-chkdeps
        "paperwork-backend >= 1.2",
        # paperwork-chkdeps take care of all the dependencies that can't be
        # handled here. For instance:
        # - Dependencies using gobject introspection
        # - Dependencies based on language (OCR data files, dictionnaries, etc)
        # - Dependencies on data files (icons, etc)
    ] + extra_deps
)

print("============================================================")
print("============================================================")
print("||                       IMPORTANT                        ||")
print("||                                                        ||")
print("||                       Please run                       ||")
print("||--------------------------------------------------------||")
print("||          paperwork-shell chkdeps paperwork_backend     ||")
print("||             paperwork-shell chkdeps paperwork          ||")
print("||                  paperwork-shell install               ||")
print("||--------------------------------------------------------||")
print("||             to find any missing dependencies           ||")
print("||       and install Paperwork's icons and shortcuts      ||")
print("============================================================")
print("============================================================")
