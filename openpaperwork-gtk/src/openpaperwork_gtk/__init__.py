import gettext


def _(s):
    return gettext.dgettext('openpaperwork_gtk', s)


CLI_PLUGINS = [
    # plugins that can make sense to use even in the CLI application
    'openpaperwork_gtk.external_apps.gio',
    'openpaperwork_gtk.fs.gio',
    'openpaperwork_gtk.l10n',
    'openpaperwork_gtk.mainloop.glib',
]

GUI_PLUGINS = [
    'openpaperwork_gtk.bug_report',
    'openpaperwork_gtk.bug_report.http',
    'openpaperwork_gtk.bug_report.zip',
    'openpaperwork_gtk.busy.mouse',
    'openpaperwork_gtk.colors',
    'openpaperwork_gtk.dialogs.single_entry',
    'openpaperwork_gtk.dialogs.yes_no',
    'openpaperwork_gtk.pixbuf.pillow',
    'openpaperwork_gtk.quit_when_all_windows_closed',
    'openpaperwork_gtk.resources',
    'openpaperwork_gtk.screenshots',
    'openpaperwork_gtk.uncaught_exception',
    'openpaperwork_gtk.wait_for_background_tasks',
    'openpaperwork_gtk.widgets.calendar',
    'openpaperwork_gtk.widgets.progress',
]
