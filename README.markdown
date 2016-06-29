# Paperwork


## Description

Paperwork is a personal document manager for scanned documents (and PDFs).

It's designed to be easy and fast to use. The idea behind Paperwork
is "scan & forget": You should be able to just scan a new document and
forget about it until the day you need it again.

In other words, let the machine do most of the work for you.


## Screenshots

### Main Window

<a href="http://youtu.be/goEgIiq2Tuc">
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

* [GNU/Linux Archlinux](doc/install.archlinux.markdown)
* [GNU/Linux Debian](doc/install.debian.markdown)
* [GNU/Linux Fedora](doc/install.fedora.markdown)
* [GNU/Linux Gentoo](doc/install.gentoo.markdown)
* [GNU/Linux Ubuntu](doc/install.debian.markdown)
* [Docker](doc/install.docker.markdown)
* [Development](doc/install.devel.markdown)

## Contact/Help

* [Extra documentation / FAQ / Tips / Wiki](https://github.com/jflesch/paperwork/wiki)
* [Mailing-list](https://github.com/jflesch/paperwork/wiki/Contact#mailing-list) (be careful: [By default, Google groups set your subscription to "no email"](https://productforums.google.com/forum/#!topic/apps/3OUlPmzKCi8))
* [Bug trackers](https://github.com/jflesch/paperwork/wiki/Contact#bug-trackers)


## Details

Papers are organized into documents. Each document contains pages.

It mainly uses:

* [Sane](http://www.sane-project.org/)/[Pyinsane](https://github.com/jflesch/pyinsane/): To scan the pages
* [Tesseract](http://code.google.com/p/tesseract-ocr/)/[Pyocr](https://github.com/jflesch/pyocr/): To extract the words from the pages (OCR)
* [GTK](http://www.gtk.org/): For the user interface
* [Whoosh](https://pypi.python.org/pypi/Whoosh/): To index and search documents, and provide keyword suggestions
* [Simplebayes](https://pypi.python.org/pypi/simplebayes/): To guess the labels
* [Pillow](https://pypi.python.org/pypi/Pillow/): Image manipulation


## Licence

GPLv3 or later. See COPYING.


## Archives

Github can automatically provide .tar.gz and .zip files if required. However,
they are not required to install Paperwork. They are indicated here as a
convenience for package maintainers.

* [Paperwork 0.3.2](https://github.com/jflesch/paperwork/archive/0.3.2.tar.gz)
* [Paperwork 0.3.1.1](https://github.com/jflesch/paperwork/archive/0.3.1.1.tar.gz)
* [Paperwork 0.3.1](https://github.com/jflesch/paperwork/archive/0.3.1.tar.gz)
* [Paperwork 0.3.0.1](https://github.com/jflesch/paperwork/archive/0.3.0.1.tar.gz)
* [Paperwork 0.3.0](https://github.com/jflesch/paperwork/archive/0.3.0.tar.gz)
* [Paperwork 0.2.5](https://github.com/jflesch/paperwork/archive/0.2.5.tar.gz)
* [Paperwork 0.2.4](https://github.com/jflesch/paperwork/archive/0.2.4.tar.gz)
* [Paperwork 0.2.3](https://github.com/jflesch/paperwork/archive/0.2.3.tar.gz)
* [Paperwork 0.2.2](https://github.com/jflesch/paperwork/archive/0.2.2.tar.gz)
* [Paperwork 0.2.1](https://github.com/jflesch/paperwork/archive/0.2.1.tar.gz)
* [Paperwork 0.2](https://github.com/jflesch/paperwork/archive/0.2.tar.gz)
* [Paperwork 0.1.3](https://github.com/jflesch/paperwork/archive/0.1.3.tar.gz)
* [Paperwork 0.1.2](https://github.com/jflesch/paperwork/archive/0.1.2.tar.gz)
* [Paperwork 0.1.1](https://github.com/jflesch/paperwork/archive/0.1.1.tar.gz)
* [Paperwork 0.1](https://github.com/jflesch/paperwork/archive/0.1.tar.gz)


## Development

All the information can be found on [the wiki](https://github.com/jflesch/paperwork/wiki#for-developers)
