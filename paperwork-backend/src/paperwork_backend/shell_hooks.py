import logging
import subprocess

import openpaperwork_core
import paperwork_backend.sync


LOGGER = logging.getLogger(__name__)


__all__ = [
    "Plugin",
]


class DocTransactionHooks(paperwork_backend.sync.BaseTransaction):
    def __init__(self, plugin, total_expected):
        super().__init__(plugin.core, total_expected)
        self.plugin = plugin
        self.plugin._run_hook("on_sync_before")

    def add_doc(self, doc_id):
        self.plugin._run_hook("on_doc_add", doc_id)
        super().add_doc(doc_id)

    def upd_doc(self, doc_id):
        self.plugin._run_hook("on_doc_upd", doc_id)
        super().upd_doc(doc_id)

    def del_doc(self, doc_id):
        self.plugin._run_hook("on_doc_del", doc_id)
        super().del_doc(doc_id)

    def commit(self):
        self.plugin._run_hook("on_sync_success")
        super().commit()

    def cancel(self):
        self.plugin._run_hook("on_sync_failed")
        super().cancel()


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            "shell_hooks",
            "syncable",
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'doc_tracking',
                'defaults': ['paperwork_backend.doctracker'],
            },
        ]

    def init(self, core):
        super().init(core)
        self._register_config("on_sync_before")
        self._register_config("on_doc_add")
        self._register_config("on_doc_upd")
        self._register_config("on_doc_del")
        self._register_config("on_sync_success")
        self._register_config("on_sync_failed")

        self.core.call_all(
            "doc_tracker_register",
            "shell_hooks",
            lambda sync, total_expected: DocTransactionHooks(self, total_expected),
        )

    def _register_config(self, hook_name):
        opt = self.core.call_success(
            "config_build_simple",
            "shell_hooks", hook_name, lambda: ""
        )
        self.core.call_all("config_register", f"shell_hook_{hook_name}", opt)

    def _run_hook(self, hook_name, *args):
        cmd = self.core.call_success("config_get", f"shell_hook_{hook_name}")
        if cmd is None:
            return
        cmd = cmd.strip()
        if cmd == "":
            return
        cmd_log = f'{hook_name} -> [{cmd} {" ".join(args)}]'
        LOGGER.info("%s ...", cmd_log)
        r = subprocess.run(
            [cmd] + list(args),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if r.returncode == 0:
            stdout = r.stdout.strip()
            for line in stdout.split("\n"):
                LOGGER.info("%s: %s", cmd_log, line)
            LOGGER.info("%s: returncode=0 (success)", cmd_log)
        else:
            for line in r.stdout:
                LOGGER.error("%s: %s", cmd_log, line)
            LOGGER.error("%s: returncode=%d", cmd_log, r.returncode)
