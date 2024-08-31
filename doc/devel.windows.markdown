# Paperwork development on Windows


## Build dependencies

Paperwork build is based on [Msys2](https://www.msys2.org/).

You must first compile and install [Libinsane](https://doc.openpaper.work/libinsane/latest/libinsane/install.html) in your MSYS2 environment.

You can have a look at the
[.gitlab-ci.yml](https://gitlab.gnome.org/World/OpenPaperwork/paperwork/blob/develop/.gitlab-ci.yml)
(target `windows_exe`) to have an exhaustive list of all the required MSYS2 packages.
Some Python packages are automatically downloaded and installed by setuptools when running
`make install` / `make install_py` / `python3 ./setup.py install` / etc.

Once everything is installed:

* `git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git`
* You can run `make install` (GNU Makefile) to fetch all the Python dependencies
  not listed here and install Paperwork system-wide. However, it won't create
  any shortcut or anything (the installer creates them).

Tesseract is not packaged in the same .zip than Paperwork and is not required
to build Paperwork executable and .zip. It is only required for running it.
Already-compiled version of Tesseract and its data files are available on
[download.openpaper.work](https://download.openpaper.work/tesseract/) and are
the files actually downloaded by the installer.


## Running

Once installed system-wide, you can run `paperwork-gtk`.


## Packaging

```sh
make windows_exe
```

It should create a directory 'paperwork' with all the required files, except
Tesseract. This directory can be stored in a .zip file and deploy wherever you
want.


## GDB

```sh
pacman -Sy mingw-w64-x86_64-gdb
git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git
cd paperwork
make install
gdb python3 --args python3 paperwork-gtk/src/paperwork_gtk/main.py
```

In GDB:

```
source c:\msys64\ucrt64\share\gdb\python3\python_gdb.py
r
```

To get all the C stacktraces:

```
thread apply all bt
```


## Adding Tesseract

[PyOCR](https://gitlab.gnome.org/World/OpenPaperwork/pyocr) has 2 ways to call
Tesseract. Either
by running its executable (module ```pyocr.tesseract```), or using its library
(module ```pyocr.libtesseract```). Currently, for convenience reasons, the
packaged version of Paperwork uses only ```pyocr.tesseract```.

By default, this module looks for tesseract in the PATH only, and let Tesseract
look for its data files in the default location. However, when packaged with
Pyinstaller, PyOCR will also look for tesseract in the subdirectory ```tesseract```
of the current directory (```os.path.join(os.getcwd(), 'tesseract')```). It will
also set an environment variable so Tesseract looks for its data files in
the subdirectory ```data\tessdata```.

So in the end, you can put Paperwork in a directory with the following hierarchy:

```
C:\Program Files (x86)\OpenPaper\ (for example)
|-- Paperwork\ (for example)
    |
    |-- Paperwork.exe
    |-- (...).dll
    |
    |-- Tesseract\
    |   |-- Tesseract.exe
    |   |-- (...).dll
    |
    |-- Data
        |
        |-- paperwork.svg
        |-- (...)
        |
        |-- Tessdata\
            |-- eng.traineddata
            |-- fra.traineddata
```

Note that it will only work if packaged with cx_freeze (`sys.frozen == True`).
