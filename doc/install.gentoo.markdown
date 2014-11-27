# Paperwork installation on GNU/Linux Gentoo

## Package

A package is available in [Lorelei's overlay](https://github.com/bignaux/lorelei-overlay).
Instructions to use this overlay are available on
[its Github repository wiki](https://github.com/bignaux/lorelei-overlay/wiki)


## Runtime dependencies

Some dependencies cannot be installed automatically, because they depend on your language:

You need an OCR tool. You can use Tesseract or Cuneiform. For now,
[Tesseract is strongly recommended](https://github.com/jflesch/pyocr/issues/2):

    $ sudo emerge -av tesseract

(TODO: How to install Tesseract's language-specific data files ?)

Optional, but strongly recommended:
Spell checking is used to improve page orientation detection, so:

    $ sudo emerge -av aspell-<your language>


## Running Paperwork

A shortcut should be available in the menus of your window manager (you may
have to log out first).

You can also start Paperwork by running the command 'paperwork'.
