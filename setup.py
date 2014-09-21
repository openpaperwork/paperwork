#!/usr/bin/env python

import imp
import os
import platform
import sys

from setuptools import setup

# Some modules/libraries required by Paperwork cannot be installed with pip or
# easy_install. So we will just help the user detecting what is missing and what
# must be installed

PACKAGE_TOOLS = {
    'debian': 'apt-get install',
    'fedora': 'yum install',
    'gentoo': 'emerge',
    'linuxmint': 'apt-get install',
    'ubuntu': 'apt-get install',
    'suse': 'zypper in',
}

distribution = platform.dist()
print("Detected system: %s" % " ".join(distribution))
distribution = distribution[0].lower()
if not distribution in PACKAGE_TOOLS:
    print("Warning: Unknown distribution. Can't suggest packages to install")


python_ver = [str(x) for x in sys.version_info]
print("Detected python version: %s" % ".".join(python_ver))
if python_ver[0] != "2" or python_ver[1] != "7":
    print("ERROR: Expected python 2.7 ! Got python %s"
         % ".".join(python_ver))
    sys.exit(1)


setup(name="paperwork",
      # if you change the version, don't forget to change it also in
      # src/paperwork/frontend/aboutdialog/aboutdialog.glade
      version="0.2",
      description="Grep for dead trees",
      long_description="""
Paperwork is a tool to make papers searchable.

The basic idea behind Paperwork is "scan & forget" : You should be able to
just scan a new document and forget about it until the day you need it again.
Let the machine do most of the work.
""",
      keywords="scanner ocr gui",
      url="https://github.com/jflesch/paperwork",
      download_url="https://github.com/jflesch/paperwork/archive/unstable.tar.gz",
      classifiers=[
          "Development Status :: 3 - Alpha",
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
          'paperwork.frontend.aboutdialog': 'src/paperwork/frontend/aboutdialog',
          'paperwork.frontend.doceditdialog':
              'src/paperwork/frontend/doceditdialog',
          'paperwork.frontend.import': 'src/paperwork/frontend/import',
          'paperwork.frontend.labeleditor': 'src/paperwork/frontend/labeleditor',
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
      scripts=['scripts/paperwork'],
      install_requires=[
          "Cython",
          'joblib',
          "Pillow",
          "pycountry",
          # "pycairo",  # doesn't work ?
          "pyenchant",
          "python-Levenshtein",
          "pyinsane >= 1.3.8",
          "pyocr >= 0.2.3",
          "numpy",
          "scipy",
          "scikit-learn",
          "scikit-image",
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

# look for dependency that setuptools cannot check or that are too painful to
# install with setuptools
print("")

# missing_modules is an array of
# (common_name, python_name, { "distrib": "package" })
missing_modules = []

modules = [
    ('Python GObject Introspection', 'gi',
     {
         'debian': 'python-gi',
         'fedora': 'pygobject3',
         'gentoo': 'dev-python/pygobject',
         'linuxmint': 'python-gi',
         'ubuntu': 'python-gi',
         'suse': 'python-gobject',
     },
    ),

    ('Gtk', 'gi.repository.Gtk',
     {
         'debian': 'gir1.2-gtk-3.0',
         'fedora': 'gtk3',
         'gentoo': 'x11-libs/gtk+',
         'linuxmint': 'gir1.2-gtk-3.0',
         'ubuntu': 'gir1.2-gtk-3.0',
         'suse': 'python-gtk',
     },
    ),

    # use_env_var += [ 'introspection' ]  # gentoo
    ('Glade UI', 'gi.repository.Gladeui',
     {
         'debian': 'gir1.2-gladeui-2.0',
         'fedora': 'glade3-libgladeui',
         'gentoo': 'dev-util/glade',
         'linuxmint': 'gir1.2-gladeui-2.0',
         'ubuntu': 'gir1.2-gladeui-2.0',
         'suse': 'typelib-1_0-Gladeui-2_0',
     },
    ),

    # TODO(Jflesch): check for jpeg support in PIL

    ('Poppler', 'gi.repository.Poppler',
     {
         'debian': 'gir1.2-poppler-0.18',
         'fedora': 'poppler-glib',
         'gentoo': 'app-text/poppler',
         'linuxmint': 'gir1.2-poppler-0.18',
         'ubuntu': 'gir1.2-poppler-0.18',
         'suse': 'typelib-1_0-Poppler-0_18',
     },
    ),

    ('Cairo', 'cairo',
     {
         'debian': 'python-gi-cairo',
         'fedora': 'pycairo',
         'gentoo': 'dev-python/pycairo',
         'linuxmint': 'python-gi-cairo',
         'ubuntu': 'python-gi-cairo',
         'suse': 'python-cairo',
     },
    ),
]

for module in modules:
    print("Looking for %s ..." % module[0])
    try:
        __import__(module[1])
    except ImportError:
        print ("Missing !")
        missing_modules.append(module)

# TODO(Jflesch): check for sane ?

try:
    from pyocr import pyocr
    print("Looking for OCR tool ...")
    ocr_tools = pyocr.get_available_tools()
except ImportError:
    print ("Couldn't import Pyocr. Will assume OCR tool is not installed yet")
    ocr_tools = []
if len(ocr_tools) > 0:
    print ("Looking for OCR language data ...")
    langs = ocr_tools[0].get_available_languages()
else:
    langs = []
    missing_modules.append(
        ('Tesseract', '(none)',
         {
             'debian': 'tesseract-ocr',
             'fedora': 'tesseract',
             'gentoo': 'app-text/tesseract',
             'linuxmint': 'tesseract-ocr',
             'ubuntu': 'tesseract-ocr',
         },
        )
    )

if (len(langs) <= 0):
    missing_modules.append(
        ('Tesseract language data' , '(none)',
         {
             'debian': 'tesseract-ocr-<your language>',
             'fedora': 'tesseract-langpack-<your language>',
             'linuxmint': 'tesseract-ocr-<your language>',
             'ubuntu': 'tesseract-ocr-<your language>',
         },
        )
    )


print("")
if len(missing_modules) <= 0:
    print("All dependencies have been found.")
else:
    print("")
    print("==============================")
    print("WARNING: Missing dependencies:")
    pkgs = []
    for dep in missing_modules:
        if distribution in dep[2]:
            print("  - %s (python module: %s ; %s package : %s)"
                  % (dep[0], dep[1], distribution, dep[2][distribution]))
            pkgs.append(dep[2][distribution])
        else:
            print("  - %s (python module: %s)"
                  % (dep[0], dep[1]))
    if len(pkgs) > 0:
        print("")
        print("==============================")
        print("Suggested command:")
        print("  sudo %s %s"
              % (PACKAGE_TOOLS[distribution],
                 " ".join(pkgs)))
        print("==============================")
    sys.exit(1)
