# Enable Saned

When installed using Flatpak, Paperwork runs in a container. This container prevents
Paperwork from accessing devices directly. Therefore, [Saned](https://linux.die.net/man/1/saned)
must be enabled on the host system, and connexion must be allowed from 127.0.0.1.

## The Systemd way (Debian, Ubuntu, Archlinux, Fedora, etc)

```sh
sudo sh -c "echo 127.0.0.1 >> /etc/sane.d/saned.conf"
sudo systemctl start saned.socket
```


# Nightly builds

For the nightly builds based on the branch 'stable':

```shell
flatpak --user install https://builder.openpaper.work/paperwork_stable.flatpakref
```

For the nightly builds based on the branch 'unstable' (you can install both stable
and unstable if you wish):

```shell
flatpak --user install https://builder.openpaper.work/paperwork_unstable.flatpakref
```

# Running Paperwork

Flatpak adds automatically a shortcut to your system menu.

You can also run it from the command line:

```shell
flatpak run work.openpaper.Paperwork
```

Run specifically the branch 'stable':

```shell
flatpak run work.openpaper.Paperwork//stable
```

Run specifically the branch 'unstable':

```shell
flatpak run work.openpaper.Paperwork//unstable
```

# Running paperwork-shell

```shell
flatpak run --command=paperwork-shell work.openpaper.Paperwork [args]
flatpak run --command=paperwork-shell work.openpaper.Paperwork --help
```

Examples:

```shell
flatpak run --command=paperwork-shell work.openpaper.Paperwork help import
flatpak run --command=paperwork-shell work.openpaper.Paperwork -bq import ~/tmp/pdf
```


# Build

```shell
git clone https://github.com/openpaperwork/paperwork
cd paperwork/flatpak
flatpak --user remote-add --if-not-exists gnome https://sdk.gnome.org/gnome.flatpakrepo
flatpak --user install gnome org.gnome.Sdk//3.26
flatpak --user install gnome org.gnome.Platform//3.26
make
```
