# Paperwork installation on GNU/Linux Debian or GNU/Linux Ubuntu


## Package

Currently, there is no official Debian or Ubuntu package for Paperwork.

Note that Paperwork depends on [Pillow](https://pypi.python.org/pypi/Pillow/).
Pillow may conflict with the package python-imaging (aka PIL).


## Build dependencies

    $ sudo apt-get install python-pip python-setuptools python-dev

    # Pillow build dependencies :
    $ sudo apt-get install libjpeg-dev zlib1g-dev


## Runtime dependencies

Optional:
Spell checking is used to improve page orientation detection, so:

    $ sudo apt-get install aspell-<your language>


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
