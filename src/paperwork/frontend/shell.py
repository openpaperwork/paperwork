import time


def _hook_scan(config, main_window):
    from gi.repository import GLib
    from gi.repository import Gtk

    # wait for everything to be loaded
    while not main_window.ready:
        time.sleep(1.0)

    # do scan
    time.sleep(3.0) # give time to Gtk
    GLib.idle_add(main_window.actions['single_scan'][1].do)


def scan():
    """
    Start Paperwork and immediately scan a page.
    """
    from paperwork import paperwork
    paperwork.main(hook_func=_hook_scan)


COMMANDS = {
    'scan': scan,
}
