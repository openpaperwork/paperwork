# Paperwork


## Description

Paperwork is a tool to make papers searchable.

The basic idea behind Paperwork is "scan & forget" : You should be able to just
scan a new document and forget about it until the day you need it again. Let the
machine do most of the work.


## Screenshots

### Main window

<a href="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.main_window.png">
  <img src="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.main_window.png" width="512" height="384" />
</a>

### Search suggestions

<a href="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.suggestions.png">
  <img src="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.suggestions.png" width="512" height="384" />
</a>

### Labels

<a href="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.multiple_labels.png">
  <img src="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.multiple_labels.png" width="402" height="358" />
</a>

<a href="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.label_edit.png">
  <img src="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.label_edit.png" width="512" height="384" />
</a>

### Settings window

<a href="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.settings.png">
  <img src="http://jflesch.kwain.net/~jflesch/paperwork/paperwork.alpha.settings.png" width="512" height="384" />
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
* blas-dev (required to build scipy)
* atlas-dev (required to build scipy)
* gcc-gfortran (required to build scipy)
* g++ (required to build scikit-learn)


### Runtime dependencies

For some reason, [setuptools doesn't work well with Numpy](http://projects.scipy.org/numpy/ticket/1841),
so you will have to install some dependencies yourself with python-pip:

	sudo pip install numpy scikit-learn


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


## Contact

### Mailing-list

[paperwork-gui@googlegroups.com](https://groups.google.com/d/forum/paperwork-gui)

This is the place to go if you have any questions regarding Paperwork, Pyocr, or Pyinsane.
Please write your emails in English.


### Bug tracker

[https://github.com/jflesch/paperwork/issues](https://github.com/jflesch/paperwork/issues)

Please write bug reports in English.

Here is some information usually useful in a good bug report:

* How to reproduce the problem ?
* What is the expected behavior ?
* What behavior did you get ?
* What version of Paperwork are you using ? (stable / testing / unstable)
* When run in a terminal, is there any uncatched Python exception raised ?
* How did you install Paperwork ? (virtualenv / setup.py / distribution package)
* What GNU/Linux distribution are you using ?

Additionally, the logging output of Paperwork may be useful.


## Development

See [the hacking guide](HACKING.markdown#HACKING)
