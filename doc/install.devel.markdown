# Paperwork development installation

## Dependencies

Depending on which [branch](https://github.com/jflesch/paperwork/wiki/Branches) you
are working, the build and runtime dependencies may not be the same.
Setuptools and ```paperwork-shell chkdeps``` should take care of all of them,
except ```paperwork-backend```.


## System-wide installation

```
$ mkdir -p ~/git
$ cd ~/git
$ git clone https://github.com/jflesch/paperwork-backend.git
$ cd paperwork-backend
$ git checkout unstable  # or 'testing'
$ sudo python3 ./setup.py install
$ paperwork-shell chkdeps paperwork_backend

$ cd ~/git
$ git clone https://github.com/jflesch/paperwork.git
$ cd paperwork
$ git checkout unstable  # or 'testing'
$ sudo python3 ./setup.py install
$ paperwork-shell chkdeps paperwork

# if you want to add it in the menus
$ paperwork-shell install
```

(see [the wiki as to why you probably want to work on the branch 'unstable'](https://github.com/jflesch/paperwork/wiki/Branches))


## Paperwork in a Python Virtualenv

If you intend to work on Paperwork, this is probably the most convenient way
to install safely a development version of Paperwork.

Virtualenv allows to run Paperwork in a specific environment, with the latest
versions of most of its dependencies. It also make it easier to remove it (you
just have to delete the directory containing the virtualenv). However the user
that did the installation will be the only one able to run Paperwork. No
shortcut will be installed in the menus of your window manager. Paperwork
won't be available directly on your PATH.


### Requirements

You will have to install [python-virtualenv](https://pypi.python.org/pypi/virtualenv).


### Installation

```
$ virtualenv --system-site-packages paperwork-virtualenv
$ cd paperwork-virtualenv
$ source bin/activate

# you're now in a virtualenv

$ git clone https://github.com/jflesch/paperwork-backend.git
$ cd paperwork-backend
$ git checkout unstable  # or 'testing'
$ python3 ./setup.py install
$ paperwork-shell chkdeps paperwork_backend

$ cd ..
$ git clone https://github.com/jflesch/paperwork.git
$ cd paperwork
$ git checkout unstable  # or 'testing'
$ python3 ./setup.py install
$ paperwork-shell chkdeps paperwork
```

### Note regarding the extra dependencies

Many dependencies can't be installed from Pypi or in a virtualenv. For
instance, all the libraries accessed through GObject introspection have
no package on Pypi. This is why they can only be installed in a system-wide
manner.

'paperwork-shell chkdeps paperwork_backend' and
'paperwork-shell chkdeps paperwork' can find all the missing dependencies.


### Running Paperwork

    $ python3 src/launcher.py

To restart paperwork:

    $ cd paperwork-virtualenv
    $ source bin/activate
    $ cd paperwork
    $ python3 src/launcher.py

Enjoy :-)
