Paperwork
=========

Description
-----------

Paperwork is a tool to make papers searchable.

Papers are organized into documents. Each document contains pages.

It uses mainly 3 other pieces of software:

* Sane: To scan the pages
* Cuneiform or Tesseract: To extract the words from the pages (OCR)
* GTK/Glade: For the user interface

Page orientation is automatically guessed using OCR.

Paperwork uses a custom indexation system to search documents and to provide
keyword suggestions. Since OCR is not perfect, and since some documents don't
contain useful keywords, Paperwork allows also to put labels on each document.

Screenshots
-----------

### Main window

<a href="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.main_window.png">
  <img src="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.main_window.png" width="512" height="384" />
</a>

### Page selection

<a href="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.page_list.png">
  <img src="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.page_list.png" width="512" height="384" />
</a>

### Search suggestions

<a href="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.suggestions.png">
  <img src="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.suggestions.png" width="512" height="384" />
</a>

### Label edition

<a href="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.label_edit.png">
  <img src="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.label_edit.png" width="512" height="384" />
</a>

### Settings window

<a href="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.settings.png">
  <img src="http://jflesch.kwain.net/data/images/paperwork/paperwork.alpha.settings.png" width="512" height="384" />
</a>

Licence
-------

GPLv3. See COPYING.

Dependencies
------------

* pygtk v2 (required)
	* Debian/Ubuntu package: python-gtk2
* python-glade2 (required)
	* Debian/Ubuntu package: python-glade2
* pycountry (required)
	* Debian/Ubuntu package: python-pycountry
* python-imaging (required)
	* Debian/Ubuntu package: python-imaging
* python-imaging-sane (optional for document searching ; required for scanning)
	* Debian/Ubuntu package: python-imaging-sane
* OCR (optional for document searching ; required for scanning)
  * Cuneiform (>= v1.1)
    * Debian/Ubuntu package: cuneiform
  * **Or** Tesseract (>= v3)
* pyocr (required)
	* Debian/Ubuntu package: none at the moment
	* Manual installation:
		* git clone git://github.com/jflesch/pyocr.git
		* cd pyocr
		* sudo python2 ./setup.py install

Installation
------------

	$ git clone git://github.com/jflesch/paperwork.git
	$ cd paperwork
	$ sudo python2 ./setup.py install
	$ paperwork

Enjoy :-)

Contact
-------

* Mailing-list: [paperwork-gui@googlegroups.com](mailto:paperwork-gui@googlegroups.com)
* Bug tracker: [https://github.com/jflesch/paperwork/issues](https://github.com/jflesch/paperwork/issues)

Development
-----------

### Rules

Try to stick to PEP-8 as much as possible. Mainly:

1. Lines are at most 80 characters long
2. Indentation is done using 4 spaces

### Code organisation

The code is divided following a 3-Tier architecture but uses the MVC vocabulary:

* View : The GUI itself (only .glade files for now)
* Controller :
  * Take the user action into account and change the model accordingly
  * Extract the informations from the model and inject them in the view
* Model : Backend code. Provides:
  * Document indexation
  * Keyword suggestions
  * Document modifications (labels, etc) and deletion

### Tips

If you want to make changes, here are few things that can help you:

1. You don't need to install paperwork to run it. Just run 'src/paperwork.py'.
2. Paperwork looks for a 'paperwork.conf' in the current work directory before
   looking for a '.paperwork.conf' in your home directory. So if you want to
   use a different config and/or a different set of documents for development
   than for your real-life work, just copy your '~/.paperwork.conf' to
   './paperwork.conf'. Note that the settings dialog will also take care of
   updating './paperwork.conf' instead of '~/.paperwork.conf'.
3. "pep8" is your friend
4. "pylint" is your friend: $ cd src ; pylint --rcfile=../pylintrc *.py

