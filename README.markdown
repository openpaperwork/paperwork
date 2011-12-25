Paperwork
=========

Description
-----------

Paperwork is a tool to make papers searchable.

Papers are organized into documents. Each document contains pages.

It uses mainly 2 other pieces of software:

* Sane: To scan the pages
* Tesseract: To extract the words from the pages

Page orientation is automatically guessed using Tesseract.

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

* pygtk v2
	* Debian/Ubuntu package: python-gtk2
* pycountry
	* Debian/Ubuntu package: python-pycountry
* python-imaging
	* Debian/Ubuntu package: python-imaging
* python-imaging-sane (optional)
	* Debian/Ubuntu package: python-imaging-sane
* Tesseract v3
	* Debian/Ubuntu package: none at the moment
	* Manual installation:
		* sudo apt-get install libjpeg-dev libtiff-dev
		* Download [Tesseract](http://code.google.com/p/tesseract-ocr/downloads/list)
		* tar -xvzf tesseract-\*.tar.gz
		* cd tesseract-\*
		* ./autogen.sh
		* ./configure
		* make -j4
		* sudo make install
		* sudo ldconfig
* Tesseract v3 trained data:
	* Debian/Ubuntu package: none at the moment
	* Manual installation:
		* Download the [trained data](http://code.google.com/p/tesseract-ocr/downloads/list)
		  for your language(s)
		* for file in \*.traineddata.gz; do gunzip $file ; done
		* sudo cp \*.traineddata /usr/local/share/tessdata
* python-tesseract
	* Debian/Ubuntu package: none at the moment
	* Manual installation:
		* Download [python-tesseract](https://github.com/jflesch/python-tesseract/zipball/master)
		* unzip jflesch-python-tesseract-\*.zip
		* cd jflesch-python-tesseract-\*
		* sudo python ./setup.py install

Installation
------------

Download [Paperwork](https://github.com/jflesch/paperwork/zipball/master)

	$ unzip jflesch-paperwork-*.zip
	$ cd jflesch-paperwork-*
	$ sudo ./setup.py install
	$ paperwork

Enjoy :-)

Development
-----------

### Rules

Try to stick to PEP-8 as much as possible. Mainly:

1. Lines are at most 80 characters long
2. Indentation is done using 4 spaces

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

