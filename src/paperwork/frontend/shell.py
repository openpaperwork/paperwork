from gi.repository import GLib


def _do_quit(main_window):
    GLib.idle_add(main_window.actions['quit'][1].do)
    return False


def _do_scan(config, main_window):
    scan_workflow = main_window.actions['single_scan'][1].do(
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


COMMANDS = {
    'scan': scan,
}
