import os
import os.path
import pkg_resources
import shutil

import xdg.BaseDirectory
import xdg.DesktopEntry
import xdg.IconTheme

from gi.repository import GLib


def _do_quit(main_window):
    GLib.idle_add(main_window.actions['quit'][1].do)
    return False


def _do_scan(config, main_window):
    main_window.actions['single_scan'][1].do(
        lambda: GLib.timeout_add(1000, _do_quit, main_window)
    )
    return False


def _wait_for_main_win(callback, config, main_window):
    if not main_window.ready:
        return True
    GLib.timeout_add(2000, callback, config, main_window)
    return False


def _hook_scan(config, main_window):
    GLib.timeout_add(1000, _wait_for_main_win, _do_scan, config, main_window)


def scan():
    """
    Start Paperwork and immediately scan a page.
    """
    from paperwork import paperwork
    paperwork.main(hook_func=_hook_scan, skip_workdir_scan=True)


def _install(icondir, datadir):
    ICON_SIZES = [
        16, 22, 24, 30, 32, 36, 42, 48, 50, 64, 72, 96, 100, 128, 150, 160,
        192, 256, 512
    ]
    png_src_icon_pattern = "paperwork_{}.png"
    png_dst_icon_pattern = os.path.join(
        icondir, "hicolor", "{}", "apps", "work.openpaper.Paperwork.png"
    )
    desktop_path = os.path.join(
        datadir, 'applications', 'work.openpaper.Paperwork.desktop'
    )
    appdata_path = os.path.join(
        datadir, "appdata", "work.openpaper.Paperwork.appdata.xml"
    )

    os.makedirs(os.path.dirname(desktop_path), exist_ok=True)

    to_copy = [
        (
            pkg_resources.resource_filename(
                'paperwork.frontend.data',
                png_src_icon_pattern.format(size)
            ),
            png_dst_icon_pattern.format(size),
        ) for size in ICON_SIZES
    ]
    to_copy.append(
        (
            pkg_resources.resource_filename(
                'paperwork.frontend.data',
                'work.openpaper.Paperwork.appdata.xml',
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
                    'paperwork.frontend.data', src_icon
                ),
                os.path.join(icondir, "hicolor", "scalable", "apps", dst_icon)
            )
        )

    for (src, dst) in to_copy:
        print("Installing {} ...".format(dst))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)

    print("Generating {} ...".format(desktop_path))
    entry = xdg.DesktopEntry.DesktopEntry(desktop_path)
    entry.set("GenericName", "Personal Document Manager")
    entry.set("Type", "Application")
    entry.set("Categories", "Office;Scanning;OCR;Archiving;GNOME;")
    entry.set("Terminal", "false")
    entry.set("Comment", "You can grep dead trees")
    entry.set("Exec", "paperwork")
    entry.set("Name", "Paperwork")
    entry.set("Icon", "work.openpaper.Paperwork")
    entry.set("Keywords", "document;scanner;ocr;")
    entry.write()
    print("Done")


def install():
    """
    Install Paperwork icons and shortcut.
    Files are installed in the home directory of the current user. No root
    access required.
    """
    _install(
        xdg.IconTheme.icondirs[0],
        xdg.BaseDirectory.xdg_data_dirs[0],
    )


def install_system(icon_basedir="/usr/share/icons", data_basedir="/usr/share"):
    """
    Install Paperwork icons and shortcut.
    Files are installed system-wide. Root access is required.

    Arguments:
        [<icon basedir> [<data basedir> [<appdatadir]]]

    icon basedir: default is /usr/share/icons
    data basedir: default is /usr/share
    """
    _install(icon_basedir, data_basedir)


COMMANDS = {
    'install': install,
    'install_system': install_system,
    'scan': scan,
}
