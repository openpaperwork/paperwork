import os
try:
    import pkg_resources
    PKG_RESOURCES_AVAILABLE = True
except Exception:
    PKG_RESOURCES_AVAILABLE = False
import shutil

import xdg.BaseDirectory
import xdg.DesktopEntry
import xdg.IconTheme

import openpaperwork_core

from .. import _


ICON_SIZES = [
    16, 22, 24, 30, 32, 36, 42, 48, 50, 64, 72, 96, 100, 128, 150, 160,
    192, 256, 512
]


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return []

    def cmd_complete_argparse(self, parser):
        p = parser.add_parser('install', help=_(
            "Install Paperwork icons and shortcuts"
        ))
        p.add_argument(
            "--user", "-u",
            help=_("Install everything only for the current user"),
            action="store_true"
        )
        p.add_argument("--icon_base_dir", default="/usr/share/icons")
        p.add_argument("--data_base_dir", default="/usr/share")

    def _install(self, console, icondir, datadir):
        assert PKG_RESOURCES_AVAILABLE
        png_src_icon_pattern = "paperwork_{}.png"
        png_dst_icon_pattern = os.path.join(
            icondir, "hicolor", "{size}x{size}", "apps",
            "work.openpaper.Paperwork.png"
        )
        desktop_path = os.path.join(
            datadir, 'applications', 'work.openpaper.Paperwork.desktop'
        )
        appdata_path = os.path.join(
            datadir, "metainfo", "work.openpaper.Paperwork.metainfo.xml"
        )

        os.makedirs(os.path.dirname(desktop_path), exist_ok=True)

        to_copy = [
            (
                pkg_resources.resource_filename(
                    'paperwork_gtk.data',
                    png_src_icon_pattern.format(size)
                ),
                png_dst_icon_pattern.format(size=size),
            ) for size in ICON_SIZES
        ]
        to_copy.append(
            (
                pkg_resources.resource_filename(
                    'paperwork_gtk.data',
                    'work.openpaper.Paperwork.metainfo.xml',
                ),
                appdata_path
            )
        )
        for icon in ['paperwork.svg', 'paperwork_halo.svg']:
            src_icon = icon
            dst_icon = icon
            if icon == 'paperwork.svg':
                dst_icon = 'work.openpaper.Paperwork.svg'
            to_copy.append(
                (
                    pkg_resources.resource_filename(
                        'paperwork_gtk.data', src_icon
                    ),
                    os.path.join(
                        icondir, "hicolor", "scalable", "apps", dst_icon
                    )
                )
            )

        for (src, dst) in to_copy:
            console.print("Installing {} ...".format(dst))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)

        console.print("Generating {} ...".format(desktop_path))
        entry = xdg.DesktopEntry.DesktopEntry(desktop_path)
        entry.set("GenericName", "Personal Document Manager")
        entry.set("Type", "Application")
        entry.set("Categories", "Office;Scanning;OCR;Archiving;GNOME;")
        entry.set("Terminal", "false")
        entry.set("Comment", "Grepping dead trees the easy way")
        # It's possible to add several actions to a single desktop file.
        # Ideally, we want a main "Open paperwork" and a secondary "Import
        # these files to paperwork". Unfortunately, the specification does
        # not allow specifying different MimeType= for the main and secondary
        # actions. So we always import (possibly 0) files.
        # https://specifications.freedesktop.org/desktop-entry-spec/1.5/ar01s11.html
        entry.set("Exec", "paperwork-gtk import %U")
        entry.set("Name", "Paperwork")
        entry.set("Icon", "work.openpaper.Paperwork")
        entry.set("Keywords", "document;scanner;ocr;")
        # PDF and all image formats supported by pillow
        entry.set(
            "MimeType",

            "application/pdf;"
            "image/bmp;"
            "image/gif;"
            "image/ico;"
            "image/icon;"
            "image/jp2;"
            "image/jpeg2000;"
            "image/jpeg;"
            "image/jpg;"
            "image/jpx;"
            "image/pjpeg;"
            "image/png;"
            "image/tiff;"
            "image/webp;"
            "image/x-bmp;"
            "image/x-MS-bmp;"
            "image/x-png;"
            "image/x-portable-bitmap;"
            "image/x-portable-graymap;"
            "image/x-portable-pixmap;"
            "image/x-tga;"
        )
        entry.validate()
        entry.write()
        console.print("Done")

    def cmd_run(self, console, args):
        if args.command != 'install':
            return None

        icon_base_dir = args.icon_base_dir
        data_base_dir = args.data_base_dir
        if args.user:
            icon_base_dir = xdg.IconTheme.icondirs[0]
            data_base_dir = xdg.BaseDirectory.xdg_data_dirs[0]

        self._install(console, icon_base_dir, data_base_dir)
        return True
