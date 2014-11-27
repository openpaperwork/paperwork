# Paperwork installation on GNU/Linux Fedora


## Package

Currently, there is no official Fedora package for Paperwork.

Note that Paperwork depends on [Pillow](https://pypi.python.org/pypi/Pillow/).
Pillow may conflict with the package python-imaging (aka PIL).


## Build dependencies

    $ sudo yum install python-pip python-setuptools python-devel numpy-f2py

    # Pillow build dependencies :
    $ sudo yum install libjpeg-turbo-devel zlib-devel

    # Scipy dependencies
    $ sudo yum install blas-devel atlas-devel lapack-devel gcc-fortran

    # Sciki-lean dependency
    $ sudo yum install gcc-c++

    # Scikit-image dependency
    $ sudo yum install Cython

    # PyEnchant dependency
    $ sudo yum install enchant-devel


## Runtime dependencies

For some reason,
[setuptools doesn't work well with Numpy](https://github.com/numpy/numpy/issues/2434),
so you will have to install some dependencies yourself with python-pip:

    $ sudo yum install python-pip
    $ sudo pip install pyocr
    $ sudo pip install numpy scikit-learn

Some dependencies cannot be installed automatically, because they depend on your language:

You need an OCR tool. You can use Tesseract or Cuneiform. For now,
[Tesseract is strongly recommended](https://github.com/jflesch/pyocr/issues/2):

    $ sudo yum install tesseract tesseract-langpack-<your language>

Optional, but strongly recommended:
Spell checking is used to improve page orientation detection, so:

    $ sudo yum install aspell-<your language>


## System-wide installation

    $ sudo pip install paperwork
    # This command will install Paperwork and tell you if some extra
    # dependencies are required.
    # IMPORTANT: the extra dependencies list may be drown in the output. You
    # may miss it.


## Running Paperwork

A shortcut should be available in the menus of your window manager (you may
have to log out first).

You can also start Paperwork by running the command 'paperwork'.

Enjoy :-)
