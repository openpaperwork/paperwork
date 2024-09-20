import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise

from .. import (_, deps)


LOGGER = logging.getLogger(__name__)

PATH_MAKE_BUG_REPORT = "/beacon/bug_report/create"
PATH_ADD_ATTACHMENT = "/beacon/bug_report/add_attachment"


class Sender(object):
    def __init__(self, core, http, progress, description, file_urls):
        self.core = core
        self.http = http
        self.progress = progress

        self.description = description
        self.file_urls = file_urls
        self.infos = None

        self.nb_steps = len(self.file_urls) + 2
        self.current_step = 0

    def _notify_progress(self, *args, **kwargs):
        assert self.current_step <= self.nb_steps

        if self.current_step == 0:
            txt = _("Creating bug report ...")
        else:
            txt = _("Sending bug report attachment ...")
        self.core.call_all(
            "on_progress", "bug_report_http",
            self.current_step / self.nb_steps, txt
        )
        self.progress.set_fraction(self.current_step / self.nb_steps)
        self.progress.set_text(txt)
        self.current_step += 1

    def _set_report_infos(self, infos):
        self.infos = infos

    def _str_to_http(self, file_name, string):
        data = {
            "file_name": file_name,
            "binary": string.encode("utf-8")
        }
        data.update(self.infos)
        return data

    def _file_to_http(self, file_url):
        with self.core.call_success("fs_open", file_url, "rb") as fd:
            data = {
                "file_name": self.core.call_success("fs_basename", file_url),
                "binary": fd.read()
            }
        data.update(self.infos)
        return data

    def get_promise(self):
        LOGGER.info("Will send %s", self.file_urls)

        promise = openpaperwork_core.promise.Promise(
            self.core, self._notify_progress
        )

        promise = promise.then(lambda *args, **kwargs: {
            "app_name": self.core.call_success("app_get_name"),
            "app_version": self.core.call_success("app_get_version"),
        })
        promise = promise.then(self.http.get_request_promise(
            PATH_MAKE_BUG_REPORT
        ))
        promise = promise.then(self._set_report_infos)
        promise = promise.then(self._notify_progress)

        promise = promise.then(
            self._str_to_http, "description.txt", self.description
        )
        promise = promise.then(self.http.get_request_promise(
            PATH_ADD_ATTACHMENT
        ))
        promise = promise.then(self._notify_progress)

        for file_url in self.file_urls:
            promise = promise.then(self._file_to_http, file_url)
            promise = promise.then(self.http.get_request_promise(
                PATH_ADD_ATTACHMENT
            ))
            promise = promise.then(self._notify_progress)

        return promise

    def get_report_url(self):
        return self.infos['url']


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.assistant = None
        self.file_urls = []
        self.http = None
        self.progress = None
        self.prepare_handler_id = None
        self.description = None

    def get_interfaces(self):
        return [
            'bug_report_method',
            'chkdeps',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app',
                'defaults': [],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'http_json',
                'defaults': ['openpaperwork_core.http.client'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.http = self.core.call_success(
            "http_json_get_client", "bug_report"
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(deps.GTK)

    def bug_report_complete(self, *args):
        self.core.call_all(
            "bug_report_add_method",
            _("Send automatically"),
            _("Send the bug report automatically to OpenPaper.work"),
            self._enable_http, self._disable_http,
            *args
        )

    def _enable_http(self, bug_report_widget_tree):
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "openpaperwork_gtk.bug_report", "bug_report_http.glade"
        )

        assistant = bug_report_widget_tree.get_object("bug_report_dialog")
        self.assistant = assistant

        page = self.widget_tree.get_object("bug_report_http_description_page")
        description_page = page
        assistant.append_page(page)
        assistant.set_page_complete(page, False)
        self.description = self.widget_tree.get_object(
            "bug_report_http_description_buffer"
        )
        self.description.connect(
            "changed", lambda txt_buffer: assistant.set_page_complete(
                description_page, txt_buffer.get_char_count() > 0
            )
        )

        page = self.widget_tree.get_object("bug_report_http_progress")
        self.progress = page
        assistant.append_page(page)
        assistant.set_page_complete(page, False)

        page = self.widget_tree.get_object("bug_report_http_result")
        self.page_idx = assistant.append_page(page)
        assistant.set_page_complete(page, True)
        assistant.set_page_type(page, Gtk.AssistantPageType.CONFIRM)

        self.prepare_handler_id = assistant.connect(
            "prepare", self._on_prepare
        )

    def _disable_http(self, bug_report_widget_tree):
        if self.widget_tree is None:
            return
        assistant = bug_report_widget_tree.get_object("bug_report_dialog")
        assistant.remove(self.widget_tree.get_object(
            "bug_report_http_description_page"
        ))
        assistant.remove(self.widget_tree.get_object(
            "bug_report_http_progress"
        ))
        assistant.remove(self.widget_tree.get_object(
            "bug_report_http_result"
        ))
        assistant.disconnect(self.prepare_handler_id)
        self.widget_tree = None

    def bug_report_set_file_urls_to_send(self, file_urls):
        self.file_urls = file_urls

    def _on_prepare(self, assistant, page):
        if page != self.progress:
            return
        self._send()

    def _get_description(self):
        author = self.widget_tree.get_object("bug_report_http_author")
        author = author.get_text()

        start = self.description.get_iter_at_offset(0)
        end = self.description.get_iter_at_offset(-1)
        description = self.description.get_text(start, end, False)

        return "Author: {}\n\n{}".format(author, description)

    def _send(self):
        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_busy",)
        )
        sender = Sender(
            self.core, self.http, self.progress,
            self._get_description(), self.file_urls
        )
        promise = promise.then(sender.get_promise())
        promise = promise.then(self._show_result, sender)
        promise = promise.catch(self._on_error)
        promise.schedule()

    def _show_result(self, sender):
        self.core.call_all("on_idle")

        if self.widget_tree is None:
            return
        LOGGER.info("Transfer successful")
        url = self.widget_tree.get_object("bug_report_http_url")
        url.set_markup('<a href="{url}">{url}</a>'.format(
            url=sender.get_report_url(),
        ))
        self.assistant.set_page_complete(self.progress, True)
        self.progress.set_fraction(1.0)
        self.progress.set_text(_("Success"))

        self.assistant.set_current_page(
            # no point in staying on the progress bar page
            self.assistant.get_current_page() + 1
        )

    def _on_error(self, exc):
        self.core.call_all("on_idle")

        if self.widget_tree is None:
            return

        LOGGER.error("Transfer failed", exc_info=exc)
        exc_txt = str(exc)[:256]
        txt = self.widget_tree.get_object("bug_report_http_result_txt")
        txt.set_text(_("Transfer failed:\n\n%s") % exc_txt)
        url = self.widget_tree.get_object("bug_report_http_url")
        url.set_text("")
        self.assistant.set_page_complete(self.progress, True)

        self.progress.set_fraction(1.0)
        self.progress.set_text(_("FAILED"))
        self.core.call_all("on_progress", "bug_report_http", 1.0)
