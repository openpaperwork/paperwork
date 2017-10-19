# Install nightly build

For the nightly built on the branch 'stable':

```shell
flatpak --user install https://builder.openpaper.work/paperwork_stable.flatpakref
```

For the nightly built on the branch 'unstable' (you can install both if you wish):

```shell
flatpak --user install https://builder.openpaper.work/paperwork_unstable.flatpakref
```

# Running

Run the lastest installed version:

```shell
flatpak run work.openpaper.Paperwork
```

Run stable branch:

```shell
flatpak run work.openpaper.Paperwork//stable
```

Run unstable branch:
```shell
flatpak run work.openpaper.Paperwork//unstable
```

# Build

```shell
flatpak --user remote-add --if-not-exists gnome https://sdk.gnome.org/gnome.flatpakrepo
flatpak --user install gnome org.gnome.Sdk//3.26
flatpak --user install gnome org.gnome.Platform//3.26
make
```
