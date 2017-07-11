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


## Runtime dependencies

### Paperwork

Once installed, please run ```paperwork-shell chkdeps paperwork_backend```
and ```paperwork-shell chkdeps paperwork``` to make sure all the required
depencies are installed.

You can run ```paperwork-shell install``` to add a Paperwork entry
in the menus of your desktop.


## Running Paperwork

If you used "paperwork-shell install", a shortcut should be available in the
menus of your window manager (you may have to log out first).

You can also start Paperwork by running the command 'paperwork'.

Enjoy :-)
