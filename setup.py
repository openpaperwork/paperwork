#!/usr/bin/env python

from distutils.core import setup

setup(name="Paperwork",
      version="0.1",
      description="Grep for dead trees",
      author="Jerome Flesch",
      author_email="jflesch@gmail.com",
      packages=[
          'paperwork',
          'paperwork.controller',
          'paperwork.model',
          'paperwork.model.common',
          'paperwork.model.pdf',
          'paperwork.model.img',
      ],
      package_dir={
          'paperwork': 'src/paperwork',
          'paperwork.controller': 'src/paperwork/controller',
          'paperwork.model': 'src/paperwork/model',
          'paperwork.model.common': 'src/paperwork/model/common',
          'paperwork.model.pdf': 'src/paperwork/model/pdf',
          'paperwork.model.img': 'src/paperwork/model/img',
          },
      data_files=[
          ('share/paperwork', [
            'src/paperwork/view/aboutdialog.glade',
            'src/paperwork/view/mainwindow.glade',
            'src/paperwork/view/multiscan.glade',
            'src/paperwork/view/settingswindow.glade',
            'src/paperwork/view/labeledit.glade',
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

