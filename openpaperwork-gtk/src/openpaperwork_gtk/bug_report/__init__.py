import datetime
import logging

import openpaperwork_core
import openpaperwork_core.deps

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    @classmethod
    def get_interfaces(cls):
        return [
            'gtk_bug_report_dialog',
            'gtk_window_listener',
            'screenshot_provider',
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'external_apps',
                'defaults': [
                    'openpaperwork_core.external_apps.dbus',
                    'openpaperwork_core.external_apps.windows',
                    'openpaperwork_core.external_apps.xdg',
                ],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                'interface': 'screenshot',
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.url_selected = None
        self.method_radio = None
        self.method_set_file_urls_callbacks = {}
        self.windows = []
        self.widget_tree = None

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _shorten_url(self, url):
        if "://" not in url:
            return url
        dir_path = self.core.call_success("fs_dirname", url)
        dir_name = self.core.call_success("fs_basename", dir_path)
        if dir_name is None or dir_name == "":
            return url
        file_name = self.core.call_success("fs_basename", url)
        return dir_name + "/" + file_name

    def _format_date(self, date):
        if date is None:
            return _("Now")
        return date.strftime("%c")

    def _format_timestamp(self, date):
        if date is None:
            date = datetime.datetime.now()
        return int(date.timestamp())

    def _refresh_attachment_page_complete(self, widget_tree):
        # check we have at least one entry toggled
        model = widget_tree.get_object("bug_report_model")
        assistant = widget_tree.get_object("bug_report_dialog")
        page = widget_tree.get_object("bug_report_attachment_selector")

        enabled = False
        for row in model:
            if row[0]:
                enabled = True
            if row[0] and "://" not in row[4]:
                enabled = False
                break
        assistant.set_page_complete(page, enabled)

    def _i18n_file_size(self, file_size):
        if isinstance(file_size, str) or file_size <= 0:
            return ""
        return self.core.call_success("i18n_file_size", file_size)

    def open_bug_report(self):
        self.method_radio = None
        self.url_selected = None

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "openpaperwork_gtk.bug_report", "bug_report.glade"
        )
        dialog = self.widget_tree.get_object("bug_report_dialog")

        self.core.call_all("bug_report_complete", self.widget_tree)

        self.widget_tree.get_object("bug_report_toggle_renderer").connect(
            "toggled", self._on_attachment_toggle, self.widget_tree
        )
        self.widget_tree.get_object("bug_report_treeview").connect(
            "row-activated", self._on_row_selected, self.widget_tree
        )
        self.widget_tree.get_object("bug_report_open_file").connect(
            "clicked", self._open_selected
        )

        model = self.widget_tree.get_object("bug_report_model")
        model.clear()

        inputs = {}
        self.core.call_all("bug_report_get_attachments", inputs)
        now = datetime.datetime.now()
        for (k, v) in inputs.items():
            v['id'] = k
            v['sort_date'] = (
                v['date'].timestamp()
                if v['date'] is not None
                else now.timestamp()
            )
        inputs = list(inputs.values())
        inputs.sort(
            key=lambda i: (-i['sort_date'], i['file_type'], i['file_url']),
        )
        for i in inputs:
            model.append(
                [
                    i['include_by_default'],
                    i['sort_date'],
                    self._format_date(i['date']),
                    i['file_type'],
                    i['file_url'],
                    self._shorten_url(i['file_url']),
                    i['file_size'],
                    self._i18n_file_size(i['file_size']),
                    i['id'],
                ]
            )

        for i in inputs:
            if not i['include_by_default']:
                continue
            self.core.call_all(
                "on_bug_report_attachment_selected", i['id'], self.widget_tree
            )

        if len(self.windows) > 0:
            dialog.set_transient_for(self.windows[-1])
        dialog.connect("close", self._on_close)
        dialog.connect("cancel", self._on_close)
        dialog.connect("prepare", self._on_prepare, self.widget_tree)

        dialog.set_visible(True)
        self.core.call_all("on_gtk_window_opened", dialog)
        self._refresh_attachment_page_complete(self.widget_tree)

    def close_bug_report(self):
        dialog = self.widget_tree.get_object("bug_report_dialog")
        dialog.destroy()

    def _on_attachment_toggle(self, cell_renderer, row_path, widget_tree):
        model = widget_tree.get_object("bug_report_model")
        val = not model[row_path][0]
        model[row_path][0] = val
        if val:
            self.core.call_all(
                "on_bug_report_attachment_selected",
                model[row_path][-1], widget_tree
            )
        else:
            self.core.call_all(
                "on_bug_report_attachment_unselected",
                model[row_path][-1], widget_tree
            )

        self._refresh_attachment_page_complete(widget_tree)

    def _on_row_selected(self, treeview, row_path, column, widget_tree):
        self._on_url_selected(widget_tree)

    def _on_url_selected(self, widget_tree):
        button = widget_tree.get_object("bug_report_open_file")
        treeview = widget_tree.get_object("bug_report_treeview")
        model = widget_tree.get_object("bug_report_model")
        (has_selected, model_iter) = (
            treeview.get_selection().get_selected()
        )
        if not has_selected or model_iter is None:
            button.set_sensitive(False)
            return
        self.url_selected = model[model_iter][4]
        button.set_sensitive("://" in self.url_selected)

    def _open_selected(self, button):
        self.core.call_success("external_app_open_file", self.url_selected)

    def bug_report_update_attachment(
            self, attachment_id, infos: dict, widget_tree):
        model = widget_tree.get_object("bug_report_model")
        for row in model:
            if row[-1] != attachment_id:
                continue
            if 'date' in infos:
                row[1] = self._format_timestamp(infos['date'])
                row[2] = self._format_date(infos['date'])
            if 'file_type' in infos:
                row[3] = infos['file_type']
            if 'file_url' in infos:
                row[4] = infos['file_url']
                row[5] = self._shorten_url(infos['file_url'])
            if 'file_size' in infos:
                row[6] = infos['file_size']
                row[7] = self._i18n_file_size(infos['file_size'])
            break
        self._on_url_selected(widget_tree)
        self._refresh_attachment_page_complete(widget_tree)

    def bug_report_get_attachment_file_url(self, attachment_id, widget_tree):
        model = widget_tree.get_object("bug_report_model")
        for row in model:
            if row[-1] != attachment_id:
                continue
            if "://" not in row[4]:
                return None
            return row[4]
        return None

    def _on_close(self, dialog):
        dialog.set_visible(False)
        self.core.call_all("on_gtk_window_closed", dialog)

    def bug_report_add_method(
            self, title, description,
            enable_callback, disable_callback,
            widget_tree):
        widget_tree_method = self.core.call_success(
            "gtk_load_widget_tree",
            "openpaperwork_gtk.bug_report", "bug_report_method.glade"
        )
        widget_tree_method.get_object("bug_report_method_title").set_text(
            title
        )
        widget_tree_method.get_object(
            "bug_report_method_description"
        ).set_markup(description)

        widget_tree.get_object("bug_report_methods").pack_start(
            widget_tree_method.get_object("bug_report_method"),
            expand=False, fill=False, padding=20
        )

        radio = widget_tree_method.get_object("bug_report_method_radio")
        radio.connect(
            "toggled", self._on_method_toggled,
            widget_tree, enable_callback, disable_callback
        )
        if self.method_radio is None:
            self.method_radio = radio
            enable_callback(widget_tree)
        else:
            radio.join_group(self.method_radio)
        self.method_radio.set_active(True)

    def _on_method_toggled(
            self, radio, widget_tree, enable_callback, disable_callback):
        if radio.get_active():
            enable_callback(widget_tree)
        else:
            disable_callback(widget_tree)

    def _on_prepare(self, assistant, page, widget_tree):
        self._set_file_urls(widget_tree)

    def _set_file_urls(self, widget_tree):
        model = widget_tree.get_object("bug_report_model")
        file_urls = [row[4] for row in model if row[0]]
        self.core.call_all("bug_report_set_file_urls_to_send", file_urls)

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return
        self.core.call_success(
            "screenshot_snap_widget",
            self.widget_tree.get_object("bug_report_dialog"),
            self.core.call_success("fs_join", out_dir, "bug_report.png")
        )
