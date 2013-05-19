#!/usr/bin/env python

from setuptools import setup

setup(name="Paperwork",
      version="0.1-testing",
      description="Grep for dead trees",
      long_description="""
Paperwork is a tool to make papers searchable.

The basic idea behind Paperwork is "scan & forget" : You should be able to
just scan a new document and forget about it until the day you need it again.
Let the machine do most of the work.
""",
      keywords="scanner ocr gui",
      url="https://github.com/jflesch/paperwork",
      download_url="https://github.com/jflesch/paperwork/archive/testing.zip",
      classifiers=[
          "Development Status :: 4 - Beta",
          "Environment :: X11 Applications :: GTK",
          "Intended Audience :: End Users/Desktop",
          "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
          "Operating System :: POSIX :: Linux",
          "Programming Language :: Python :: 2.7",
          "Topic :: Multimedia :: Graphics :: Capture :: Scanners",
          "Topic :: Multimedia :: Graphics :: Graphics Conversion",
          "Topic :: Scientific/Engineering :: Image Recognition",
          "Topic :: Text Processing :: Indexing",
      ],
      licenses="GPLv3+",
      author="Jerome Flesch",
      author_email="jflesch@gmail.com",
      packages=[
          'paperwork',
          'paperwork.frontend',
          'paperwork.backend',
          'paperwork.backend.common',
          'paperwork.backend.pdf',
          'paperwork.backend.img',
      ],
      package_dir={
          'paperwork': 'src/paperwork',
          'paperwork.frontend': 'src/paperwork/frontend',
          'paperwork.backend': 'src/paperwork/backend',
          'paperwork.backend.common': 'src/paperwork/backend/common',
          'paperwork.backend.pdf': 'src/paperwork/backend/pdf',
          'paperwork.backend.img': 'src/paperwork/backend/img',
          },
      data_files=[
          ('share/paperwork', [
            'src/paperwork/frontend/aboutdialog.glade',
            'src/paperwork/frontend/doceditdialog.glade',
            'src/paperwork/frontend/import.glade',
            'src/paperwork/frontend/import_select.glade',
            'src/paperwork/frontend/mainwindow.glade',
            'src/paperwork/frontend/multiscan.glade',
            'src/paperwork/frontend/pageeditingdialog.glade',
            'src/paperwork/frontend/settingswindow.glade',
            'src/paperwork/frontend/labeledit.glade',
            ]),
          ('share/locale/fr/LC_MESSAGES',
           ['locale/fr/LC_MESSAGES/paperwork.mo']),
          ('share/applications',
           ['data/paperwork.desktop']),
          ('share/icons',
           ['data/paperwork.svg']),
      ],
      scripts=['scripts/paperwork'],
      install_requires=[
          "PIL",
          "pycountry",
          "pycairo",
          "pyenchant",
          "python-Levenshtein",
          "Whoosh",
          "pyinsane",
          "pyocr",
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

