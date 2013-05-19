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

GPLv3. See COPYING.


## Dependencies

If a package is not available in your distribution, you can install the Pypi package.

* python v2.7<br/>
  Paperwork is written for Python **2.7**.
  So depending of your Linux distribution, you may have to invoke "python2"
  instead of "python" (for instance with Arch Linux)
* pygi (required):
	* Debian/Ubuntu package: python-gi
	* Gentoo package : dev-python/pygobject
	* Fedora package : pygobject3
* gtk v3 (required)
	* Debian/Ubuntu package: gir1.2-gtk-3.0
	* Gentoo package : x11-libs/gtk+
	* Fedora package : gtk3
* gladeui (required)
	* Debian/Ubuntu package: gir1.2-gladeui-2.0
	* Gentoo package : dev-util/glade (USE=+introspection)
	* Fedora package : glade3-libgladeui
* pycountry (required)
	* Debian/Ubuntu package: python-pycountry
	* Gentoo package : dev-python/pycountry
	* Fedora package : None
	* Pypi package : pycountry
* python-imaging (aka PIL) (required)
	* Debian/Ubuntu package: python-imaging
	* Gentoo package : dev-python/imaging (in future dev-python/pillow, /!\ conflict between the both packages)
	* Fedora :
		* JPEG support is missing in the Fedora package
		* You must install libjpeg-turbo-devel first
		* If you're running on a x86_64:
			* sudo ln -s /usr/lib64/libjpeg.so /usr/lib
			* sudo ln -s /usr/lib64/libjpeg.so.62 /usr/lib
			* sudo ln -s /usr/lib64/libjpeg.so.62.1.0 /usr/lib
		* sudo python-pip install PIL
	* Pypi package : PIL (you must install libjpeg-devel / libjpeg-turbo-devel first !)
* poppler (required)
	* Debian/Ubuntu package: gir1.2-poppler-0.18
	* Gentoo package : app-text/poppler
	* Fedora package : poppler-glib
* Python Cairo bindings for the GObject library (required):
	* Debian/Ubuntu package: python-gi-cairo
	* Gentoo package : dev-python/pycairo
	* Fedora package : pycairo
* python-enchant (required)
	* Debian/Ubuntu package: python-enchant
	* Gentoo package : dev-python/pyenchant
	* Fedora package : python-enchant
* python-levenshtein (required)
	* Debian/Ubuntu package: python-levenshtein
	* Gentoo package : dev-python/python-levenshtein
	* Fedora package : python-Levenshtein
* python-whoosh (required)
	* Debian/Ubuntu package: python-whoosh
	* Gentoo package : dev-python/whoosh
	* Fedora : python-pip install Whoosh
* sane (required by pyinsane):
	* Debian/Ubuntu packages : libsane libsane-extras (+ libsane-hpaio for HP printers)
	* Gentoo packages : sane-backends sane-frontends xsane
	* Fedora package : sane-backends sane-backends-drivers-scanners sane-backends-libs
* pyinsane (required)
	* Debian/Ubuntu package: none at the moment
	* Gentoo package : none at the moment
	* Fedora package : none at the moment
	* Manual installation:
		* git clone git://github.com/jflesch/pyinsane.git
		* cd pyinsane
		* sudo python ./setup.py install
* OCR (optional for document searching ; required for scanning)
	* Tesseract (>= v3.01) (recommended)
		* Debian/Ubuntu package: tesseract-ocr tesseract-ocr-&lt;your language&gt;
		* Gentoo package : app-text/tesseract
		* Fedora package : tesseract tesseract-langpack-&lt;your language&gt;
	* **Or** Cuneiform (>= v1.1)
    	* Debian/Ubuntu package: cuneiform
		* Gentoo package : app-text/cuneiform but presently =app-text/cuneiform-1.1.0-r1 is masked
		* Fedora package : cuneiform
* pyocr (required)
	* Debian/Ubuntu package: none at the moment
	* Manual installation:
		* git clone git://github.com/jflesch/pyocr.git
		* cd pyocr
		* sudo python ./setup.py install


## Installation

	$ git clone git://github.com/jflesch/paperwork.git
	$ cd paperwork
	$ sudo python ./setup.py install
	$ paperwork

Enjoy :-)


## Contact

* Mailing-list: [paperwork-gui@googlegroups.com](https://groups.google.com/d/forum/paperwork-gui)
* Bug tracker: [https://github.com/jflesch/paperwork/issues](https://github.com/jflesch/paperwork/issues)


## Development

See [the hacking guide](HACKING.markdown#HACKING)
