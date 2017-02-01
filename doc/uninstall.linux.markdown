# Paperwork uninstallation

This document assumes you installed Paperwork with Python tools (Pip or ```python3 ./setup.py install```).
If you installed it with your distribution package manager, please use it to uninstall Paperwork.


## Pip's behavior

Pip is Python package manager.

Pip may install side by side many versions of a same package. It is useful since programs
may request very specific versions of libraries. However, it creates problems when it comes to
programs and their data, and when it comes to uninstalling.

When you ask Pip to uninstall something, by default, it actually uninstall only the latest version.
So in case you had many versions you may have to run it many times.


## Uninstalling Paperwork

Libraries most likely only used by Paperwork:

```sh
sudo pip3 uninstall pyocr # run it as many times as required
sudo pip3 uninstall pyinsane2 # run it as many times as required
sudo pip3 uninstall pypillowfight # run it as many times as required
```

Paperwork itself:

```sh
sudo pip3 uninstall paperwork-backend  # run it as many times as required
sudo pip3 uninstall paperwork  # run it as many times as required
```

[Bug reports](https://github.com/jflesch/paperwork/issues/513) indicate that
Pip may loose track of data files and even not replace them later. So,
just to be safe, you can also run:

```sh
rm -f /usr/bin/paperwork /usr/local/bin/paperwork
rm -f /usr/bin/paperwork-shell /usr/local/bin/paperwork-shell
rm -rf /usr/share/paperwork /usr/local/share/paperwork
```


## Uninstalling Paperwork's libraries

Many libraires have been created especially for Paperwork.

These libraries may be used by other programs installed with Pip, and there
is no easy way to know which ones. When in doubt, it's usually safer to just
keep them installed (they don't take much space ; they don't have much data
files). It's also usually safe to uninstall them just to update them next.

```sh
sudo pip3 uninstall pyocr  # run it as many times as required
sudo pip3 uninstall pyinsane2  # run it as many times as required
sudo pip3 uninstall pypillowfight  # run it as many times as required
```
