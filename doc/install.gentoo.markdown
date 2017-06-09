# Paperwork installation on GNU/Linux Gentoo

## Package

    $ emerge paperwork

## Runtime dependencies

Some dependencies cannot be installed automatically. You can find all the
missing dependencies by running 'paperwork-chkdeps'

    $ paperwork-shell chkdeps paperwork_backend
    $ paperwork-shell chkdeps paperwork

Since Paperwork 1.2, you can add a Paperwork shortcut in your desktop menus
with the following command:

    $ paperwork-shell install


## Running Paperwork

If you used "paperwork-shell install", a shortcut should be available in the
menus of your window manager (you may have to log out first).

You can also start Paperwork by running the command 'paperwork'.
