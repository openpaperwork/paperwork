# Paperwork - [openpaper.work](https://openpaper.work/)


## Description

Paperwork is a personal document manager. It manages scanned documents and PDFs.

It's designed to be easy and fast to use. The idea behind Paperwork
is "scan & forget": You can just scan a new document and
forget about it until the day you need it again.

In other words, let the machine do most of the work for you.


## Screenshots

### Main Window

<a href="http://youtu.be/RMazTTM6ltg">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.3/main_window.png" width="447" height="262" />
</a>


### Search Suggestions

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.3/suggestions.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.3/suggestions.png" width="155" height="313" />
</a>


### Labels

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.3/multiple_labels.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.3/multiple_labels.png" width="187" height="262" />
</a>


### Settings window

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.3/settings.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.3/settings.png" width="443" height="286" />
</a>


## Main features

* Scan
* Automatic detection of page orientation
* OCR
* Document labels
* Automatic guessing of the labels to apply on new documents
* Search
* Keyword suggestions
* Quick edit of scans
* PDF support


## Installation

Note regarding updates:
If you're upgrading from a previous version installed with pip, it is strongly recommended you uninstall
it first before installing the new version.

* [GNU/Linux Archlinux](doc/install.archlinux.markdown)
* [GNU/Linux Debian](doc/install.debian.markdown)
* [GNU/Linux Fedora](doc/install.fedora.markdown)
* [GNU/Linux Gentoo](doc/install.gentoo.markdown)
* [GNU/Linux Ubuntu](doc/install.debian.markdown)
* [Docker](doc/install.docker.markdown)
* [GNU/Linux Development](doc/install.devel.markdown)
* Windows: [Installation](https://openpaper.work) / [Development](doc/devel.windows.markdown)


## Uninstall

### GNU/Linux

[Doc](doc/uninstall.linux.markdown)

### Windows

If you used the installer from [OpenPaper](https://openpaper.work), Paperwork can be uninstalled like any
other Windows application (something like Control Panel --> Applications --> Uninstall).

If you installed it manually (for development), you can follow the same process than for
[GNU/Linux](doc/uninstall.linux.markdown)


## Donate

<a href="https://flattr.com/submit/auto?fid=0ywr1d&url=https%3A%2F%2Fopenpaper.work">
<img src="https://button.flattr.com/flattr-badge-large.png" alt="Flattr this" title="Flattr this" border="0">
</a>


## Contact/Help

* [Extra documentation / FAQ / Tips / Wiki](https://github.com/jflesch/paperwork/wiki)
* [Mailing-list](https://github.com/jflesch/paperwork/wiki/Contact#mailing-list) (be careful: [By default, Google groups set your subscription to "no email"](https://productforums.google.com/forum/#!topic/apps/3OUlPmzKCi8))
* [Bug trackers](https://github.com/jflesch/paperwork/wiki/Contact#bug-trackers)


## Details

Papers are organized into documents. Each document contains pages.

It mainly uses:

* [Sane](http://www.sane-project.org/)/[Pyinsane](https://github.com/jflesch/pyinsane/#readme): To scan the pages
* [Tesseract](https://github.com/tesseract-ocr)/[Pyocr](https://github.com/jflesch/pyocr/#readme): To extract the words from the pages (OCR)
* [GTK](http://www.gtk.org/): For the user interface
* [Whoosh](https://pypi.python.org/pypi/Whoosh/): To index and search documents, and provide keyword suggestions
* [Simplebayes](https://pypi.python.org/pypi/simplebayes/): To guess the labels
* [Pillow](https://pypi.python.org/pypi/Pillow/)/[Libpillowfight](https://github.com/jflesch/libpillowfight#readme): Image manipulation


## Automated tests

Paperwork has automated tests. These tests are designed in a unusual manner:
They use screenshots (aka "May work or may not work. Do you feel lucky today ?").
Because these screenshots change often and are heavy (compared to source files),
they are stored in a separate Git repository:
[paperwork-tests](https://github.com/jflesch/paperwork-tests#readme)


## Licence

GPLv3 or later. See COPYING.


## Development

All the information can be found on [the wiki](https://github.com/jflesch/paperwork/wiki#for-developers)
