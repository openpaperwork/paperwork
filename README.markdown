# Paperwork


## Description

Paperwork is a tool to make easily papers searchable.

The basic idea behind Paperwork is "scan & forget" : You should be able to just
scan a new document and forget about it until the day you need it again. Let the
machine do most of the work.

Paperwork also supports PDF and images import.


## Screenshots

### Main window

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/main_window.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/main_window.png" width="512" height="384" />
</a>

### Search suggestions

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/suggestions.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/suggestions.png" width="512" height="384" />
</a>

### Labels

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/multiple_labels.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/multiple_labels.png" width="402" height="358" />
</a>

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/label_edit.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/label_edit.png" width="512" height="384" />
</a>

### Settings window

<a href="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/settings.png">
  <img src="https://raw.github.com/jflesch/paperwork-screenshots/master/0.1/settings.png" width="512" height="384" />
</a>


## Details

Papers are organized into documents. Each document contains pages.

It uses mainly 3 other pieces of software:

* Sane: To scan the pages
* Cuneiform or Tesseract: To extract the words from the pages (OCR)
* GTK/Glade: For the user interface

Page orientation is automatically guessed using OCR.

Paperwork uses a custom indexation system to search documents and to provide
keyword suggestions. Since OCR is not perfect, and since some documents don't
contain useful keywords, Paperwork allows also to put labels on each document.


## Licence

GPLv3 or later. See COPYING.


## Installation

* [GNU/Linux Archlinux](doc/install.archlinux.markdown)
* [GNU/Linux Debian](doc/install.debian.markdown)
* [GNU/Linux Fedora](doc/install.fedora.markdown)
* [GNU/Linux Gentoo](doc/install.gentoo.markdown)
* [Development](doc/install.devel.markdown)

## Archives

Github can automatically provides .tar.gz and .zip files if required. However,
they are not required to install Paperwork. They are indicated here as a
convenience for package maintainers.

* [Paperwork 0.1.2](https://github.com/jflesch/paperwork/archive/0.1.2.tar.gz)
* [Paperwork 0.1.1](https://github.com/jflesch/paperwork/archive/0.1.1.tar.gz)
* [Paperwork 0.1](https://github.com/jflesch/paperwork/archive/0.1.tar.gz)


## Contact/Help

* [Extra documentation / FAQ / Tips / Wiki](https://github.com/jflesch/paperwork/wiki)
* [Mailing-list](https://github.com/jflesch/paperwork/wiki/Contact#mailing-list)
* [Bug trackers](https://github.com/jflesch/paperwork/wiki/Contact#bug-trackers)


## Development

All the information can be found on [the wiki](https://github.com/jflesch/paperwork/wiki#for-developers)
