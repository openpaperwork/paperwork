#!/usr/bin/env python

from distutils.core import setup

setup(name="Paperwork",
      version="0.1",
      description="Grep for dead trees",
      author="Jerome Flesch",
      author_email="jflesch@gmail.com",
      packages=['paperwork'],
      package_dir={ 'paperwork': 'src' },
      data_files=[
          ('share/paperwork', [
            'src/aboutdialog.glade',
            'src/mainwindow.glade',
            'src/settingswindow.glade',
            'src/labeledit.glade',
            ]),
          ('share/locale/fr/LC_MESSAGES',
           ['locale/fr/LC_MESSAGES/paperwork.mo']),
          ('share/applications',
           ['src/paperwork.desktop']),
          ('share/icons',
           ['src/paperwork.svg']),
      ],
      scripts=['scripts/paperwork'],
     )

