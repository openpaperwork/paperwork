# Quick start

## Debian >= jessie / Ubuntu >= 16.04

```sh
# Install Flatpak and Saned
sudo apt install flatpak sane-utils

# Enable Saned (required for scanning ; allow connexion from the loopback only)
sudo sh -c "echo 127.0.0.1 >> /etc/sane.d/saned.conf"
sudo systemctl start saned.socket

# Install Paperwork (for the current user only)
flatpak --user install https://builder.openpaper.work/paperwork_stable.flatpakref

# Start Paperwork
flatpak run work.openpaper.Paperwork
```

# Updating Paperwork

```sh
flatpak --user update
```

# Details

## Saned

When installed using Flatpak, Paperwork runs in a container. This container prevents
Paperwork from accessing devices directly. Therefore, [Saned](https://linux.die.net/man/1/saned),
the scanning daemon, must be enabled on the host system, and connexion must be allowed from 127.0.0.1.

## Nightly builds

For the nightly builds based on the branch 'stable':

```shell
flatpak --user install https://builder.openpaper.work/paperwork_stable.flatpakref
```

For the nightly builds based on the branch 'unstable' (you can install both stable
and unstable if you wish):

```shell
flatpak --user install https://builder.openpaper.work/paperwork_unstable.flatpakref
```

## Running Paperwork

Flatpak adds automatically a shortcut to your system menu.

You can also run it from the command line:

```shell
flatpak run work.openpaper.Paperwork
```

You can run specifically the branch 'stable':

```shell
flatpak run work.openpaper.Paperwork//stable
```

You can also run specifically the branch 'unstable':

```shell
flatpak run work.openpaper.Paperwork//unstable
```

## Running paperwork-shell

When using Flatpak, paperwork-shell remains available. Note that it will run inside Paperwork's container, and may not access files outside your home directory.

```shell
flatpak run --command=paperwork-shell work.openpaper.Paperwork [args]
flatpak run --command=paperwork-shell work.openpaper.Paperwork --help
```

Examples:

```shell
flatpak run --command=paperwork-shell work.openpaper.Paperwork help import
flatpak run --command=paperwork-shell work.openpaper.Paperwork -bq import ~/tmp/pdf
```


## Build

```shell
git clone https://github.com/openpaperwork/paperwork
cd paperwork/flatpak
flatpak --user remote-add --if-not-exists gnome https://sdk.gnome.org/gnome.flatpakrepo
flatpak --user install gnome org.gnome.Sdk//3.26
flatpak --user install gnome org.gnome.Platform//3.26
make
```
