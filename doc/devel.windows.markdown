# Paperwork development on Windows


## Build dependencies

It's hard to list all the dependencies here. Currently, the main ones are:

* [Python 3.4](https://www.python.org/downloads/windows/)
* Windows SDK7.1 : See [Python wiki](https://wiki.python.org/moin/WindowsCompilers#Microsoft_Visual_C.2B-.2B-_10.0_standalone:_Windows_SDK_7.1_.28x86.2C_x64.2C_ia64.29)
* [Pillow](http://www.lfd.uci.edu/~gohlke/pythonlibs/#pillow)
* [Python-levenshtein](www.lfd.uci.edu/~gohlke/pythonlibs/#python-levenshtein)
* [GObject Introspection, Gtk, Gdk, Libpoppler, & friends](https://sourceforge.net/projects/pygobjectwin32/)
* etc

They must be installed *before* the rest of Paperwork. Once everything is installed:

* [Clone](https://git-for-windows.github.io/):
  * ```https://github.com/jflesch/paperwork.git```
  * ```https://github.com/jflesch/paperwork-backend.git```
* Backend can be installed like any Python library (```python setup.py install```). It should
  install a bunch of dependencies as well.
* On the frontend, you can run ```python ./setup.py install``` to fetch all the dependencies
  not listed here. However, it won't create any shortcut or anything. Paperwork startup script
  is installed, but isn't of much help.


## Running

Frontend can be started like on GNU/Linux. Go to where you checked out Paperwork frontend,
and run ```python src/launcher.py```.
