import datetime
import json
import logging
import uuid

import openpaperwork_core
import openpaperwork_core.promise

from . import PeriodicTask
from .. import _


LOGGER = logging.getLogger(__name__)

POST_STATS_INTERVAL = datetime.timedelta(days=7)
POST_STATS_PATH = "/beacon/post_statistics"


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            "bug_report_attachments",
            "stats_post",
        ]

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app',
                'defaults': ['paperwork_backend.app'],
            },
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'fs',
                'defaults': [
                    'openpaperwork_core.fs.memory',
                    'openpaperwork_core.fs.python',
                ],
            },
            {
                'interface': 'http_json',
                'defaults': ['openpaperwork_core.http.client'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.periodic = PeriodicTask(
            "statistics",
            datetime.timedelta(days=7),
            self.stats_send
        )
        self.http = self.core.call_success(
            "http_json_get_client", "statistics"
        )

        self._register_config(core)
        self.periodic.register_config(core)

        if self.core.call_success("config_get", "send_statistics"):
            self.periodic.do(core)

    def _register_config(self, core):
        setting = self.core.call_success(
            "config_build_simple", "statistics",
            "enabled", lambda: False
        )
        self.core.call_all(
            "config_register", "send_statistics", setting
        )
        setting = self.core.call_success(
            "config_build_simple", "statistics",
            "uuid", lambda: uuid.getnode()
        )
        self.core.call_all("config_register", "uuid", setting)

    def _collect_stats(self, node_uuid):
        stats = {
            'uuid': node_uuid,
            'paperwork_version': self.core.call_success("app_get_version"),
            'nb_documents': 0,
            'os_name': '',
            'platform_architecture': '',
            'platform_processor': '',
            'platform_distribution': '',
            'cpu_count': 0,
        }
        self.core.call_all("stats_get", stats)
        return {'statistics': stats}

    def stats_send(self):
        node_uuid = self.core.call_success("config_get", "uuid")
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._collect_stats, args=(node_uuid,)
        )
        promise = promise.then(self.http.get_request_promise(POST_STATS_PATH))

        def on_request_done(reply):
            LOGGER.info("Statistics posted. Reply: {}".format(reply))
            self.core.call_all('on_stats_sent')

        promise = promise.then(on_request_done)
        promise = promise.catch(self._on_stats_send_error)
        promise.schedule()

    def _on_stats_send_error(self, exc):
        LOGGER.warning("Failed to send stats", exc_info=exc)

    def bug_report_get_attachments(self, out: dict):
        out['stats'] = {
            'include_by_default': True,
            'date': None,
            'file_type': _("App. & system info."),
            'file_url': _("Select to generate"),
            'file_size': 0,
        }

    def _write_stats_to_tmp_file(self, stats):
        stats = json.dumps(
            stats, indent=4, separators=(",", ": "), sort_keys=True
        )
        (file_url, fd) = self.core.call_success(
            "fs_mktemp", prefix="statistics_", suffix=".json", mode="w",
            on_disk=True
        )
        with fd:
            fd.write(stats)
        return file_url

    def on_bug_report_attachment_selected(self, attachment_id, *args):
        if attachment_id != 'stats':
            return

        self.core.call_all(
            "bug_report_update_attachment", attachment_id,
            {"file_url": _("Collecting statistics ...")},
            *args
        )

        node_uuid = self.core.call_success("config_get", "uuid")
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._collect_stats, args=(node_uuid,)
        )
        promise = promise.then(self._write_stats_to_tmp_file)
        promise = promise.then(
            lambda file_url: self.core.call_all(
                "bug_report_update_attachment", attachment_id, {
                    'file_url': file_url,
                    'file_size': self.core.call_success(
                        'fs_getsize', file_url
                    ),
                }, *args
            )
        )
        promise.schedule()
