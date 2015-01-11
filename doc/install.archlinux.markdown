# Paperwork installation on GNU/Linux ArchLinux


## Package

A package is available in [AUR](https://aur.archlinux.org/packages/paperwork/).

If there is a problem with the package, please report it on
[the mailing-list](https://github.com/jflesch/paperwork/wiki/Contact#mailing-list).
Please do **not** report issue with packages on Paperwork's bugtracker. It is
**not** possible to assign issues to package maintainer on the bugtracker.

## Manual installation

See the [Fedora](install.fedora.markdown) or [Debian](install.debian.markdown) installation
guides for reference.

Please note that there is a key difference between ArchLinux and other
distributions: It's using Python 3.x by default instead of Python 2.7.
So you must replace the following commands:

* pip / python-pip --> pip2.7
* python --> python2.7


## Runtime dependencies

### Paperwork &gt;= 0.2.1

Once installed, please run 'paperwork-chkdeps' to make sure all the required depencies are installed.

### Paperwork &lt;= 0.2.0

Some dependencies cannot be installed automatically, because they depend on your language:

You need an OCR tool. You can use Tesseract or Cuneiform. For now,
[Tesseract is strongly recommended](https://github.com/jflesch/pyocr/issues/2):

    $ sudo pacman -S tesseract tesseract-data-<your language>

Optional, but strongly recommended:
Spell checking is used to improve page orientation detection, so:

    $ sudo pacman -S aspell-<your language>



## Running Paperwork

A shortcut should be available in the menus of your window manager (you may
have to log out first).

You can also start Paperwork by running the command 'paperwork'.

Enjoy :-)
