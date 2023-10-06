import argparse
import logging
import sys

import openpaperwork_core  # noqa: E402
import openpaperwork_gtk  # noqa: E402

import paperwork_backend  # noqa: E402

# this import must be non-relative due to cx_freeze running this .py
# as an independant Python script
from paperwork_gtk import _  # noqa: E402


LOGGER = logging.getLogger(__name__)

REQUIRED_PLUGINS = (
    'openpaperwork_core.logs.print',
    # plugin 'uncaught_exceptions' requires a mainloop plugin
    'openpaperwork_gtk.mainloop.glib',
)

DEFAULT_GUI_PLUGINS = (
    paperwork_backend.DEFAULT_PLUGINS +
    openpaperwork_gtk.GUI_PLUGINS +
    [
        'openpaperwork_core.display.print',
        'openpaperwork_core.logs.print',
        'openpaperwork_core.spatial.rtree',
        'openpaperwork_gtk.drawer.pillow',
        'openpaperwork_gtk.drawer.scan',
        'openpaperwork_gtk.gesture.autoscrolling',
        'openpaperwork_gtk.gtk_init',
        'paperwork_backend.docscan.autoselect_scanner',
        'paperwork_backend.guesswork.cropping.calibration',
        'paperwork_gtk.about',
        'paperwork_gtk.actions.app.find',
        'paperwork_gtk.actions.app.help',
        'paperwork_gtk.actions.app.open_about',
        'paperwork_gtk.actions.app.open_bug_report',
        'paperwork_gtk.actions.app.open_settings',
        'paperwork_gtk.actions.app.open_shortcuts',
        'paperwork_gtk.actions.doc.add_to_selection',
        'paperwork_gtk.actions.doc.delete',
        'paperwork_gtk.actions.doc.export',
        'paperwork_gtk.actions.doc.new',
        'paperwork_gtk.actions.doc.open_external',
        'paperwork_gtk.actions.doc.prev_next',
        'paperwork_gtk.actions.doc.print',
        'paperwork_gtk.actions.doc.properties',
        'paperwork_gtk.actions.doc.redo_ocr',
        'paperwork_gtk.actions.docs.delete',
        'paperwork_gtk.actions.docs.export',
        'paperwork_gtk.actions.docs.properties',
        'paperwork_gtk.actions.docs.redo_ocr',
        'paperwork_gtk.actions.docs.select_all',
        'paperwork_gtk.actions.page.copy_text',
        'paperwork_gtk.actions.page.delete',
        'paperwork_gtk.actions.page.edit',
        'paperwork_gtk.actions.page.export',
        'paperwork_gtk.actions.page.move_inside_doc',
        'paperwork_gtk.actions.page.move_to_doc',
        'paperwork_gtk.actions.page.print',
        'paperwork_gtk.actions.page.redo_ocr',
        'paperwork_gtk.actions.page.reset',
        'paperwork_gtk.cmd.import',
        'paperwork_gtk.cmd.install',
        'paperwork_gtk.doc_selection',
        'paperwork_gtk.docimport',
        'paperwork_gtk.drawer.calibration',
        'paperwork_gtk.drawer.frame',
        'paperwork_gtk.flatpak',
        'paperwork_gtk.gesture.drag_and_drop',
        'paperwork_gtk.gesture.zoom',
        'paperwork_gtk.icon',
        'paperwork_gtk.keyboard_shortcut.zoom',
        'paperwork_gtk.l10n',
        'paperwork_gtk.mainwindow.doclist',
        'paperwork_gtk.mainwindow.doclist.labeler',
        'paperwork_gtk.mainwindow.doclist.name',
        'paperwork_gtk.mainwindow.doclist.thumbnailer',
        'paperwork_gtk.mainwindow.docproperties',
        'paperwork_gtk.mainwindow.docproperties.extra_text',
        'paperwork_gtk.mainwindow.docproperties.labels',
        'paperwork_gtk.mainwindow.docproperties.name',
        'paperwork_gtk.mainwindow.docview',
        'paperwork_gtk.mainwindow.docview.controllers.autoscrolling',
        'paperwork_gtk.mainwindow.docview.controllers.click',
        'paperwork_gtk.mainwindow.docview.controllers.drop',
        'paperwork_gtk.mainwindow.docview.controllers.empty_doc',
        'paperwork_gtk.mainwindow.docview.controllers.layout',
        'paperwork_gtk.mainwindow.docview.controllers.page_number',
        'paperwork_gtk.mainwindow.docview.controllers.scroll',
        'paperwork_gtk.mainwindow.docview.controllers.title',
        'paperwork_gtk.mainwindow.docview.controllers.zoom',
        'paperwork_gtk.mainwindow.docview.drag',
        'paperwork_gtk.mainwindow.docview.pageadd.buttons',
        'paperwork_gtk.mainwindow.docview.pageadd.import',
        'paperwork_gtk.mainwindow.docview.pageadd.scan',
        'paperwork_gtk.mainwindow.docview.pageadd.source_popover',
        'paperwork_gtk.mainwindow.docview.pageinfo',
        'paperwork_gtk.mainwindow.docview.pageinfo.actions',
        'paperwork_gtk.mainwindow.docview.pageinfo.layout_settings',
        'paperwork_gtk.mainwindow.docview.pageprocessing',
        'paperwork_gtk.mainwindow.docview.pageview',
        'paperwork_gtk.mainwindow.docview.pageview.boxes',
        'paperwork_gtk.mainwindow.docview.pageview.boxes.all',
        'paperwork_gtk.mainwindow.docview.pageview.boxes.hover',
        'paperwork_gtk.mainwindow.docview.pageview.boxes.search',
        'paperwork_gtk.mainwindow.docview.pageview.boxes.selection',
        'paperwork_gtk.mainwindow.docview.progress',
        'paperwork_gtk.mainwindow.docview.scanview',
        'paperwork_gtk.mainwindow.exporter',
        'paperwork_gtk.mainwindow.home',
        'paperwork_gtk.mainwindow.pageeditor',
        'paperwork_gtk.mainwindow.search.advanced',
        'paperwork_gtk.mainwindow.search.field',
        'paperwork_gtk.mainwindow.search.suggestions',
        'paperwork_gtk.mainwindow.window',
        'paperwork_gtk.menus.app.help',
        'paperwork_gtk.menus.app.open_about',
        'paperwork_gtk.menus.app.open_bug_report',
        'paperwork_gtk.menus.app.open_settings',
        'paperwork_gtk.menus.app.open_shortcuts',
        'paperwork_gtk.menus.doc.add_to_selection',
        'paperwork_gtk.menus.doc.delete',
        'paperwork_gtk.menus.doc.export',
        'paperwork_gtk.menus.doc.open_external',
        'paperwork_gtk.menus.doc.print',
        'paperwork_gtk.menus.doc.properties',
        'paperwork_gtk.menus.doc.redo_ocr',
        'paperwork_gtk.menus.docs.delete',
        'paperwork_gtk.menus.docs.export',
        'paperwork_gtk.menus.docs.properties',
        'paperwork_gtk.menus.docs.redo_ocr',
        'paperwork_gtk.menus.docs.select_all',
        'paperwork_gtk.menus.page.copy_text',
        'paperwork_gtk.menus.page.delete',
        'paperwork_gtk.menus.page.export',
        'paperwork_gtk.menus.page.move_inside_doc',
        'paperwork_gtk.menus.page.move_to_doc',
        'paperwork_gtk.menus.page.print',
        'paperwork_gtk.menus.page.redo_ocr',
        'paperwork_gtk.menus.page.reset',
        'paperwork_gtk.model.help',
        'paperwork_gtk.model.help.intro',
        'paperwork_gtk.new_doc',
        'paperwork_gtk.notifications.dialog',
        'paperwork_gtk.notifications.notify',
        'paperwork_gtk.print',
        'paperwork_gtk.settings',
        'paperwork_gtk.settings.ocr.selector_popover',
        'paperwork_gtk.settings.ocr.settings',
        'paperwork_gtk.settings.scanner.calibration',
        'paperwork_gtk.settings.scanner.dev_id_popover',
        'paperwork_gtk.settings.scanner.flatpak',
        'paperwork_gtk.settings.scanner.mode_popover',
        'paperwork_gtk.settings.scanner.resolution_popover',
        'paperwork_gtk.settings.scanner.settings',
        'paperwork_gtk.settings.stats',
        'paperwork_gtk.settings.storage',
        'paperwork_gtk.settings.update',
        'paperwork_gtk.shortcuts.app.find',
        'paperwork_gtk.shortcuts.doc.new',
        'paperwork_gtk.shortcuts.doc.prev_next',
        'paperwork_gtk.shortcuts.doc.print',
        'paperwork_gtk.shortcuts.doc.properties',
        'paperwork_gtk.shortcuts.page.copy_text',
        'paperwork_gtk.shortcuts.page.edit',
        'paperwork_gtk.shortcutswin',
        'paperwork_gtk.sync_on_start',
        'paperwork_gtk.update_notification',
        'paperwork_gtk.widget.flowlayout',
        'paperwork_gtk.widget.label',
    ]
)


class DefaultConsole:
    def print(self, text):
        print(text)

    def input(self, prompt=""):
        return input(prompt)


def gtk_main(app, options, core):
    app = core.call_success("gtk_get_app")
    if app.get_is_remote():
        LOGGER.info("passing control to main paperwork instance")
    # if paperwork is already running, focus it, otherwise remain in this
    # process
    app.activate()
    return 0


def main_main(in_args):
    # To load the plugins, we need first to load the configuration plugin
    # to get the list of plugins to load.
    # The configuration plugin may write traces using logging, so we better
    # enable and configure the plugin logs.print first.

    core = openpaperwork_core.Core()
    for module_name in REQUIRED_PLUGINS:
        core.load(module_name)
    for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
        core.load(module_name)
    core.init()
    core.call_all(
        "init_logs", "paperwork-gtk",
        "info" if len(in_args) <= 0 else "warning"
    )

    core.call_all("config_load")
    core.call_all("config_load_plugins", "paperwork-gtk", DEFAULT_GUI_PLUGINS)

    if len(in_args) <= 0:
        core.call_all("gtk_init", gtk_main, core)
    else:
        # we remain in this process and call the plugin requested by the
        # command line
        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help=_('command'), dest='command', required=True
        )
        core.call_all("cmd_complete_argparse", cmd_parser)
        args = parser.parse_args(in_args)
        console = DefaultConsole()
        core.call_all("cmd_set_console", console)
        core.call_all("cmd_run", console, args)

    return 0


def main():
    main_main(sys.argv[1:])


if __name__ == "__main__":
    # Do not remove. Cx_freeze goes through here
    main()
