#!/usr/bin/env python3

import glob
import os
import sys

import cx_Freeze


quiet = '--quiet' in sys.argv or '-q' in sys.argv
freeze = 'build_exe' in sys.argv

kwargs = {}

common_include_files = []

required_dll_search_paths = os.getenv("PATH", os.defpath).split(os.pathsep)
required_dlls = [
    'libatk-1.0-0.dll',
    'libepoxy-0.dll',
    'libgdk-3-0.dll',
    'libgdk_pixbuf-2.0-0.dll',
    'libgtk-3-0.dll',
    'libhandy-1-0.dll',
    'libinsane.dll',
    'libinsane_gobject.dll',
    'libintl-8.dll',
    'libnotify-4.dll',
    'libpango-1.0-0.dll',
    'libpangocairo-1.0-0.dll',
    'libpangoft2-1.0-0.dll',
    'libpangowin32-1.0-0.dll',
    'libpoppler-*.dll',
    'libpoppler-glib-8.dll',
    'librsvg-2-2.dll',
    'libsqlite3-0.dll',
    'libxml2-2.dll',
]

for dll in required_dlls:
    dll_path = None
    for p_dir in required_dll_search_paths:
        p_glob = os.path.join(p_dir, dll)
        for p in glob.glob(p_glob):
            if os.path.isfile(p):
                dll_path = p
                break
        if dll_path is not None:
            break
    if dll_path is None:
        raise Exception(
            "Unable to locate {} in {}".format(
                dll, required_dll_search_paths
            )
        )
    print(f"Found {dll} = {dll_path}")
    common_include_files.append((dll_path, os.path.basename(dll_path)))

# We need the .typelib files at runtime.
# The related .gir files are in $PREFIX/share/gir-1.0/$NS.gir,
# but those can be omitted at runtime.

required_gi_namespaces = [
    "Atk-1.0",
    "cairo-1.0",
    "Gdk-3.0",
    "GdkPixbuf-2.0",
    "Gio-2.0",
    "GLib-2.0",
    "GModule-2.0",
    "GObject-2.0",
    "Gtk-3.0",
    "Handy-1",
    "HarfBuzz-0.0",
    "Notify-0.7",
    "Pango-1.0",
    "PangoCairo-1.0",
    "Poppler-0.18",
    "freetype2-2.0",

    "Libinsane-1.0",
]

for ns in required_gi_namespaces:
    subpath = "lib/girepository-1.0/{}.typelib".format(ns)
    fullpath = os.path.join(sys.prefix, subpath)
    assert os.path.isfile(fullpath), (
        "Required file {} is missing" .format(
            fullpath,
        ))
    common_include_files.append((fullpath, subpath))

common_packages = [
    "gi",   # always seems to be needed
    "cairo",   # Only needed (for foreign structs) if no "import cairo"s

    # XXX(Jflesch): bug ?
    "pyocr",
    "pyocr.libtesseract",
    "setuptools",

    "openpaperwork_core",
    "openpaperwork_gtk",
    "paperwork_backend",
    "paperwork_gtk",
    "paperwork_shell",
]

kwargs['executables'] = [
    cx_Freeze.Executable(
        script="src/paperwork_gtk/main.py",
        target_name="paperwork.exe",
        base=("Console" if os.name != "nt" else "Win32GUI"),
    ),
    cx_Freeze.Executable(
        # UGLY
        script="../paperwork-shell/src/paperwork_shell/main.py",
        target_name="paperwork-json.exe",
        base="Console",
    ),
]
kwargs['options'] = {
    "build_exe": {
        'include_files': common_include_files,
        'silent': True,
        'packages': common_packages,
        "excludes": ["tkinter", "tk", "tcl"],
    },
}
kwargs["setup_requires"] = [
    "setuptools_scm",
]
kwargs["use_scm_version"] = True

cx_Freeze.setup(**kwargs)
