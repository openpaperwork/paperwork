# Paperwork-shell

![Paperwork-shell demo](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/search.gif)


## Introduction

Paperwork-shell provides 2 commands:

* `paperwork-cli`: Human-friendly command line interface. For instance, it
  can be useful if you want to use Paperwork through SSH.
* `paperwork-json`: Designed to be used in scripts. Results can be parsed in
  shell scripts using [`jq`](https://stedolan.github.io/jq/).

Both commands takes the same arguments as input. Only their outputs differ.

From there, `paperwork-xxx` means either `paperwork-cli` or `paperwork-json`.


## OS/distribution specifics

### On Windows

Only paperwork-json is available.

Installer doesn't modify your PATH. If you want to invoke paperwork-json,
you either have to modify your PATH yourself, or use the command
full path (ex: `"c:\program files (x86)\Paperwork\paperwork-json.exe"`).


### In a Flatpak container

You have to run the commands from inside the Flatpak container.

```sh
flatpak run --command="paperwork-cli" work.openpaper.Paperwork <arguments>
```

For examples:

```sh
flatpak run --command="paperwork-cli" work.openpaper.Paperwork "--help"
flatpak run --command="paperwork-cli" work.openpaper.Paperwork chkdeps
```


## Sub-commands

Paperwork-shell's commands expect sub-commands (similar to `git`). You can
obtain all the sub-commands and their expected arguments using `--help`
(long help) or `-h` (short help).

Not all sub-commands are described in this README. Available sub-commands may
vary based on what plugins are enabled or not. This README is just here
to give you a preview of the most common sub-commands usually available.


### chkdeps

```sh
$ paperwork-cli chkdeps
Detected system: debian 10 buster
Nothing to do.
```

Check for dependencies required by *paperwork-shell*'s plugins. It does NOT
check for dependencies required by *paperwork-gtk*'s plugins (for that, try
`paperwork-gtk chkdeps` instead).

If dependencies are missing, it will try to provide the command to install
them.


### config

```sh
$ paperwork-cli config show
send_statistics = True
uuid = 1234567890
statistics_last_run = 1970-01-01
statistics_protocol = https
statistics_server = openpaper.work
statistics_url = /beacon/post_statistics
workdir = file:///home/jflesch/papers
scanner_dev_id = libinsane:sane:epson2:net:192.168.42.18
scanner_source_id = flatbed
scanner_resolution = 300
ocr_lang = fra
check_for_update = True
last_update_found = 1.3.0-253-g032699cf
update_last_run = 1970-01-01
update_protocol = https
update_server = openpaper.work
update_url = /beacon/latest

$ paperwork-cli config get workdir
workdir = file:///home/jflesch/papers

$ paperwork-cli config put workdir str file:///home/jflesch/tmp/papers
workdir = file:///home/jflesch/tmp/papers
```

`paperwork-xxx config` provides various sub-sub-commands to read and modify
Paperwork config and enable/disable `paperwork-shell`'s plugins.

The one most important settings is the work directory path: `workdir`. It
indicates where documents managed by Paperwork must be stored. It *must* be
an URL (`file://xxx`).


### plugins

```sh
$ paperwork-cli plugins list
openpaperwork_core.logs.print
openpaperwork_gtk.mainloop.glib
openpaperwork_core.config
paperwork_backend.beacon.stats
paperwork_backend.beacon.sysinfo
(...)
paperwork_shell.display.print
paperwork_shell.display.progress
paperwork_shell.display.scanpaperwork_shell.display.print
paperwork_shell.display.progress
paperwork_shell.display.scan
```

While most settings are shared between Paperwork UIs (paperwork-shell and
paperwork-gtk), plugins lists are *not*. If you want to modify
`paperwork-gtk`'s plugin list, you have to use `paperwork-gtk plugins` instead.

If you want to enable or disable features, you can simply add or remove
the corresponding plugin. For instance, to disable the automatic OCR run
on imported documents or scanned pages:

```sh
$ paperwork-cli plugins remove paperwork_backend.guesswork.ocr.pyocr
Plugin paperwork_backend.guesswork.ocr.pyocr removed
```

`paperwork-cli plugins remove` and `paperwork-cli plugins add` take
dependencies into account: `remove` will also remove all the plugins
that depends on the one you're removing. `add` will also add all the
plugins required for the one you're adding.

Some plugins are mandatory and cannot be disabled (mainly all the plugins
required to read the configuration file).

If something go wrong, you can reset the plugin list to its default
with `paperwork-cli plugins reset`.


### sync

![Paperwork-cli sync](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/sync.webm)

Update the content of search engine index, label guesser training, etc,
according to the current content of the work directory.

If you modify the content of your work directory manually (without using
Paperwork commands), this is the command to run.

This operation is also executed every time `paperwork-gtk` is started.


### search

![Paperwork-xxx search](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/search.gif)

Returns documents that contains keywords identical or close to the one
specified. If no keyword is specified, all the documents are returned.

Results are always ordered by decreasing dates.


### show

![paperwork-cli show 1](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/show_1.png)
![paperwork-cli show 1](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/show_2.png)

Show a document page images and texts.


### scanner

```sh
% paperwork-cli scanner list

BROTHER DS-620 (sheetfed scanner ; sane:dsseries:usb:0x04F9:0x60E0)
 |-- ID: libinsane:sane:dsseries:usb:0x04F9:0x60E0
 |-- Source: feeder
 |    |-- Resolutions: [75, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325,
                        350, 375, 400, 425, 450, 475, 500, 525, 550, 575, 600]

Canon CanoScan N1240U/LiDE30 (flatbed scanner ; sane:plustek:libusb:001:024)
 |-- ID: libinsane:sane:plustek:libusb:001:024
 |-- Source: flatbed (Normal)
 |    |-- Resolutions: [150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400,
 |    |                 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675,
 |    |                 700, 725, 750, 775, 800, 825, 850, 875, 900, 925, 950,
 |    |                 975, 1000, 1025, 1050, 1075, 1100, 1125, 1150, 1175,
 |    |                 1200, 1225, 1250, 1275, 1300, 1325, 1350, 1375, 1400,
 |    |                 1425, 1450, 1475, 1500, 1525, 1550, 1575, 1600, 1625,
 |    |                 1650, 1675, 1700, 1725, 1750, 1775, 1800, 1825, 1850,
 |    |                 1875, 1900, 1925, 1950, 1975, 2000, 2025, 2050, 2075,
 |    |                 2100, 2125, 2150, 2175, 2200, 2225, 2250, 2275, 2300,
 |    |                 2325, 2350, 2375, 2400]
 |-- Source: flatbed (Transparency)
 |    |-- Resolutions: [150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400,
 |    |                 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675,
 |    |                 700, 725, 750, 775, 800, 825, 850, 875, 900, 925, 950,
 |    |                 975, 1000, 1025, 1050, 1075, 1100, 1125, 1150, 1175,
 |    |                 1200, 1225, 1250, 1275, 1300, 1325, 1350, 1375, 1400,
 |    |                 1425, 1450, 1475, 1500, 1525, 1550, 1575, 1600, 1625,
 |    |                 1650, 1675, 1700, 1725, 1750, 1775, 1800, 1825, 1850,
 |    |                 1875, 1900, 1925, 1950, 1975, 2000, 2025, 2050, 2075,
 |    |                 2100, 2125, 2150, 2175, 2200, 2225, 2250, 2275, 2300,
 |    |                 2325, 2350, 2375, 2400]
 |-- Source: flatbed (Negative)
 |    |-- Resolutions: [150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400,
 |    |                 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675,
 |    |                 700, 725, 750, 775, 800, 825, 850, 875, 900, 925, 950,
 |    |                 975, 1000, 1025, 1050, 1075, 1100, 1125, 1150, 1175,
 |    |                 1200, 1225, 1250, 1275, 1300, 1325, 1350, 1375, 1400,
 |    |                 1425, 1450, 1475, 1500, 1525, 1550, 1575, 1600, 1625,
 |    |                 1650, 1675, 1700, 1725, 1750, 1775, 1800, 1825, 1850,
 |    |                 1875, 1900, 1925, 1950, 1975, 2000, 2025, 2050, 2075,
 |    |                 2100, 2125, 2150, 2175, 2200, 2225, 2250, 2275, 2300,
 |    |                 2325, 2350, 2375, 2400]

Epson PID 08C1 (flatbed scanner ; sane:epson2:net:192.168.42.18)
 |-- ID: libinsane:sane:epson2:net:192.168.42.18
 |-- Source: flatbed
 |    |-- Resolutions: [75, 100, 150, 300, 600]


% paperwork-cli scanner set "libinsane:sane:epson2:net:192.168.42.18"
Default source: flatbed
ID: libinsane:sane:epson2:net:192.168.42.18
Source: flatbed
Resolution: 300
```

Provides subcommands to list the available scanners and get and set the scanner
to use and its settings. When configuring the scanner, it checks that the
provided settings are actually consistent with what the scanner provides. You
can bypass those checks by using `paperwork-cli config` instead.

If you get warnings and errors from the Libinsane, you can safely ignore them
unless you didn't get the scanner you were looking for in the list.


### scan

![Paperwork-xxx scan](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/scan.webm)

Scan all the page(s) available in the scanner. Append all the pages to the
specified document (`-d`). If no document is specified, a new one will be
created.

If you get warnings and errors from the Libinsane, you can safely ignore them
unless the scan didn't work.


### import

```sh
$ paperwork-cli import 100227398115.pdf
Importing ['100227398115.pdf'] ...
[index_update        ] Indexing new document 20191113_1255_32
Committing changes in label guesser database ... Done
Committing changes in the index ... Done
Done
Import result:
- Imported files: {'file:///home/jflesch/tmp/pdf/100227398115.pdf'}
- Non-imported files: set()
- New documents: {'20191113_1255_32'}
- Updated documents: set()
- PDF: 1
- Documents: 1
```

Import images of PDF files.

Images are appended to the specified document (`-d`). If no document is
specified, a new one is created.

PDF are always imported as a new document, even if a document ID is specified.


### label

![paperwork-cli label list](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/label_1.png)
![paperwork-cli label add](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/label_2.png)

Add and remove labels on documents.

When adding a label, if the label already exists on other documents,
the existing color will be reused. If it does not exist yet, either
the user has specified a color (`-c #abcdef`), or a random one will be
generated.


### edit

![paperwork-cli edit -m rotate\_clockwise](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/edit.gif)

Basic editing of page images.

Modifiers must be specified. Many can provided in one shot so the OCR is only
run once.


### reset

![paperwork-cli reset](http://storage.sbg.cloud.ovh.net/v1/AUTH_6c4273c748b243c58df3f6942075e0c9/gitlab.gnome.org/paperwork-shell/reset.gif)

Returns a page image to its initial state. It will also cancel any changes made
by post-processing plugins after importing or scanning.


### delete

```sh
$ paperwork-cli delete 20191113_1255_32
Delete document 20191113_1255_32 ? [y/N] y
Deleting document 20191113_1255_32 ...

$ paperwork-cli delete 20191112_2117_09 -p 1
Delete page(s) [1] of document 20191112_2117_09 ? [y/N] y
Deleting page 1 of document 20191112_2117_09 ...
[WARNING] [paperwork_backend.model.workdir] All pages of document
     file:///home/jflesch/tmp/papers/20191112_2117_09 have been removed.
     Removing document
```

Delete page(s) or a whole document.


### export

```sh
$ paperwork-cli export 20191107_2343_44
Current filters: []
Next possible filters:
- img_boxes

$ paperwork-cli export 20191107_2343_44 -f img_boxes
Current filters: ['img_boxes']
Next possible filters:
- unpaper
- swt_soft
- swt_hard
- generated_pdf
- bw
- grayscale
- bmp
- gif
- jpeg
- png
- tiff

$ paperwork-cli export 20191107_2343_44 -f img_boxes -f generated_pdf
Current filters: ['img_boxes', 'generated_pdf']
'generated_pdf' is an output filter. Not other filter can be added after 'generated_pdf'.

$ paperwork-cli export 20191107_2343_44 -f img_boxes -f generated_pdf -o ~/tmp/out.pdf
Exporting to file:///home/jflesch/tmp/out.pdf ... Done
```

Export a document or page(s).

An export is seen as processing pipeline (in other words, filter list).
Selecting a document or a page (`-p`) represent the input or the pipe.
Various processing components (pipes) can be chained. Some of them can be
used at the end of the pipe. There are restrictions on which components
can follow each other.

For instances:

- Somewhere before `generated_pdf`, you must have a component `img_boxes`
  to turn the input document or page(s) into a bunch of images and text boxes.
- Only a PDF document can be used as input for the component `unmodified_pdf`
  and no other components can precede it.


## Shell scripts

You can have a look at [some examples of Bash scripts](../scripts).


## paperwork-cli and stdout redirection

In case you want to redirect stdout but also want to keep the ANSI output,
you can set
[the environment variable `FORCE_COLOR=1`](https://rich.readthedocs.io/en/stable/console.html#environment-variables).
