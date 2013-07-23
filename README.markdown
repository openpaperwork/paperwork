# Paperwork


## Description

Paperwork is a tool to make papers searchable.

The basic idea behind Paperwork is "scan & forget" : You should be able to just
scan a new document and forget about it until the day you need it again. Let the
machine do most of the work.


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


## Manual Installation

If you want to install a stable version of Paperwork, please first check that your Linux
distribution doesn't already have a package for it.

### Build dependencies

If you're installing Paperwork yourself, you will probably need to install first some build dependencies:

* python-setuptools (required by the setup.py script of Paperwork)
* python-dev (required to build some dependencies)
* libjpeg-dev (required to have JPEG support built in the Pillow library)


### System-wide installation

This is the most convenient way to install Paperwork manually.

Note that Paperwork depends on [Pillow](https://pypi.python.org/pypi/Pillow/).
Pillow may conflict with python-imaging (aka PIL).

You will need python-pip. Python-pip is invoked with 'pip' or 'python-pip',
depending of your GNU/Linux distribution.

	$ sudo pip install "git+git://github.com/jflesch/paperwork.git#egg=paperwork"
	# This command will install Paperwork and tell you if some extra dependencies
	# are required. (note that the dependencies list may be drown in the
	# output ... :/)
	<install the extra dependencies>

To (re)start paperwork:

	$ paperwork

A shortcut should also be available in the menus of your window manager (you
may have to log out first).

Enjoy :-)


### Installation in a virtualenv

If you intend to work on Paperwork, this is probably the most convenient way
to install a development version of Paperwork.

Virtualenv allows to run Paperwork in a specific environment, with the latest
versions of most of its dependencies. It also make it easier to remove it (you
just have to delete the directory containing the virtualenv). However the user
that did the installation will be the only one able to run Paperwork. No
shortcut will be installed in the menus of your window manager. Paperwork
won't be available directly on your PATH.

You will have to install [python-virtualenv](https://pypi.python.org/pypi/virtualenv).

	$ virtualenv --system-site-packages paperwork-virtualenv
	$ cd paperwork-virtualenv
	$ source bin/activate
	# you're now in a virtualenv
	$ git clone git://github.com/jflesch/paperwork.git
	$ cd paperwork
	$ python ./setup.py install
	# This script will install Paperwork and tell you if some extra dependencies
	# are required
	<install the extra dependencies>
	$ src/launcher.py

To restart paperwork:

	$ cd paperwork-virtualenv
	$ source bin/activate
	$ cd paperwork
	$ src/launcher.py

Enjoy :-)


### Note regarding the extra dependencies

Many dependencies can't be installed from Pypi or in a virtualenv. For
instance, all the libraries accessed through GObject introspection have
no package on Pypi. This is why they can only be installed in a system-wide
manner.
The setup.py will indicate what is required and how to install it.


## Contact

* [Mailing-list](https://github.com/jflesch/paperwork/wiki/Contact#mailing-list)
* [Bug trackers](https://github.com/jflesch/paperwork/wiki/Contact#bug-trackers)


## Development

All the information can be found on [the wiki](https://github.com/jflesch/paperwork/wiki#for-developers)
