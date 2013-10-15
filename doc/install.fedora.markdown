# Paperwork installation on GNU/Linux Fedora


## Package

Currently, there is no official Fedora package for Paperwork.

Note that Paperwork depends on [Pillow](https://pypi.python.org/pypi/Pillow/).
Pillow may conflict with the package python-imaging (aka PIL).


## Build dependencies

    $ sudo yum install python-pip python-setuptools python-devel

    # Pillow build dependencies :
    $ sudo yum install libjpeg-turbo-devel zlib-devel


## System-wide installation

    $ sudo pip install paperwork
    # This command will install Paperwork and tell you if some extra
    # dependencies are required.
    # IMPORTANT: the extra dependencies list may be drown in the output. You
    # may miss it.


## Runtime dependencies

Optional:
Spell checking is used to improve page orientation detection, so:

    $ sudo apt-get install aspell-<your language>


## Running Paperwork

A shortcut should be available in the menus of your window manager (you may
have to log out first).

You can also start Paperwork by running the command 'paperwork'.

Enjoy :-)
