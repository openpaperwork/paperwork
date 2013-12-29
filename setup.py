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
      version="0.1.2",
      description="Grep for dead trees",
      long_description="""
Paperwork is a tool to make papers searchable.

The basic idea behind Paperwork is "scan & forget" : You should be able to
just scan a new document and forget about it until the day you need it again.
Let the machine do most of the work.
""",
      keywords="scanner ocr gui",
      url="https://github.com/jflesch/paperwork",
      download_url="https://github.com/jflesch/paperwork/archive/stable.tar.gz",
      classifiers=[
          "Development Status :: 5 - Production/Stable",
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
          (os.path.join(sys.prefix, 'share/paperwork'), [
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
          "nltk",
          "Pillow",
          "pycountry",
          # "pycairo",  # doesn't work ?
          "pyenchant",
          "Whoosh",
          "pyinsane >= 1.1.0",
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

# look for dependency that setuptools cannot check

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
         'ubuntu': 'python-gi',
         'suse': 'python-gobject',
     },
    ),
    ('Gtk', 'gi.repository.Gtk',
     {
         'debian': 'gir1.2-gtk-3.0',
         'fedora': 'gtk3',
         'gentoo': 'x11-libs/gtk+',
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
         'ubuntu': 'gir1.2-poppler-0.18',
         'suse': 'typelib-1_0-Poppler-0_18',
     },
    ),
    ('Cairo', 'cairo',
     {
         'debian': 'python-gi-cairo',
         'fedora': 'pycairo',
         'gentoo': 'dev-python/pycairo',
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
    print "Couldn't import Pyocr. Will assume OCR tool is not installed yet"
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
    print("")
