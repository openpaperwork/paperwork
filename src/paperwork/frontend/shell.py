import time


def _hook_scan(config, main_window):
    from gi.repository import GLib
    from gi.repository import Gtk

    # wait for everything to be loaded
    had_to_wait = True
    while had_to_wait:
        had_to_wait = False
        for scheduler in main_window.schedulers.values():
            had_to_wait |= scheduler.wait_for_all()
        had_to_wait |= Gtk.events_pending()
        if had_to_wait:
            time.sleep(0.5)  # give some CPU time to Gtk

    # do scan
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
