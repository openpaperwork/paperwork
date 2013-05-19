#!/usr/bin/env python

from setuptools import setup

setup(name="Paperwork",
      version="0.1",
      description="Grep for dead trees",
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
     )

