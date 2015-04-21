# Paperwork


## Description

Paperwork is a personal document manager for scanned documents (and PDFs).

It's designed to be easy and fast to use. The idea behind Paperwork
is "scan & forget": You should be able to just scan a new document and
forget about it until the day you need it again.

In other words, let the machine do most of the work for you.


## Screenshots

### Main Window &amp; Scan

<a href="http://youtu.be/goEgIiq2Tuc">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.2/main_window.png" width="512" height="347" />
</a>

### Search Suggestions

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.2/suggestions.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.2/suggestions.png" width="512" height="349" />
</a>

### Labels

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.2/multiple_labels.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.2/multiple_labels.png" width="450" height="557" />
</a>

### Settings window

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.2/settings.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.2/settings.png" width="512" height="374" />
</a>


## Details

Papers are organized into documents. Each document contains pages.

It uses mainly 4 other pieces of software:

* [Sane](http://www.sane-project.org/): To scan the pages
* [Tesseract](http://code.google.com/p/tesseract-ocr/): To extract the words from the pages (OCR)
* [GTK](http://www.gtk.org/)/[Glade](https://glade.gnome.org/): For the user interface
* [Whoosh](https://pypi.python.org/pypi/Whoosh/): To index and search documents, and provide keyword suggestions

Page orientation is automatically guessed using OCR.

Since OCR is not perfect, and since some documents don't contain useful keywords, 
Paperwork allows also to put labels on each document.


## Licence

GPLv3 or later. See COPYING.


## Installation

* [GNU/Linux Archlinux](doc/install.archlinux.markdown)
* [GNU/Linux Debian](doc/install.debian.markdown)
* [GNU/Linux Fedora](doc/install.fedora.markdown)
* [GNU/Linux Gentoo](doc/install.gentoo.markdown)
* [GNU/Linux Ubuntu](doc/install.debian.markdown)
* [Development](doc/install.devel.markdown)


## Archives

Github can automatically provides .tar.gz and .zip files if required. However,
they are not required to install Paperwork. They are indicated here as a
convenience for package maintainers.

* [Paperwork 0.2.4](https://github.com/jflesch/paperwork/archive/0.2.4.tar.gz)
* [Paperwork 0.2.3](https://github.com/jflesch/paperwork/archive/0.2.3.tar.gz)
* [Paperwork 0.2.2](https://github.com/jflesch/paperwork/archive/0.2.2.tar.gz)
* [Paperwork 0.2.1](https://github.com/jflesch/paperwork/archive/0.2.1.tar.gz)
* [Paperwork 0.2](https://github.com/jflesch/paperwork/archive/0.2.tar.gz)
* [Paperwork 0.1.3](https://github.com/jflesch/paperwork/archive/0.1.3.tar.gz)
* [Paperwork 0.1.2](https://github.com/jflesch/paperwork/archive/0.1.2.tar.gz)
* [Paperwork 0.1.1](https://github.com/jflesch/paperwork/archive/0.1.1.tar.gz)
* [Paperwork 0.1](https://github.com/jflesch/paperwork/archive/0.1.tar.gz)


## Contact/Help

* [Extra documentation / FAQ / Tips / Wiki](https://github.com/jflesch/paperwork/wiki)
* [Mailing-list](https://github.com/jflesch/paperwork/wiki/Contact#mailing-list)
* [Bug trackers](https://github.com/jflesch/paperwork/wiki/Contact#bug-trackers)


## Development

All the information can be found on [the wiki](https://github.com/jflesch/paperwork/wiki#for-developers)
