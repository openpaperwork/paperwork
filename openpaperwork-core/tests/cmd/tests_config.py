import argparse
import unittest

import openpaperwork_core
import openpaperwork_core.cmd


class MockConfigBackendModule:
    """
    Plugin paperwork_backend.config uses openpaperwork.config_file.
    This mock mocks openpaperwork.config_file so we can test
    paperwork_backend.config.file
    """
    __name__ = "openpaperwork_core.config.backend.configparser"

    class Plugin(openpaperwork_core.PluginBase):
        @classmethod
        def get_interfaces(cls):
            return ["config_backend"]

        def __init__(self, core):
            super().__init__(core)
            self.calls = []
            self.returns = {}
            self.config_backend_load = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_load', args, kwargs)
            )
            self.config_backend_save = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_save', args, kwargs)
            )
            self.config_backend_load_plugins = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_load_plugins', args, kwargs)
            )
            self.config_backend_add_plugin = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_add_plugin', args, kwargs)
            )
            self.config_backend_remove_plugin = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_remove_plugin', args, kwargs)
            )
            self.config_backend_put = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_put', args, kwargs)
            )
            self.config_backend_get = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_get', args, kwargs)
            )
            self.config_backend_add_observer = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_add_observer', args, kwargs)
            )
            self.config_backend_remove_observer = (
                lambda *args, **kwargs:
                self._handle_call(
                    'config_backend_remove_observer', args, kwargs
                )
            )
            self.config_backend_list_active_plugins = (
                lambda *args, **kwargs:
                self._handle_call(
                    'config_backend_list_active_plugins', args, kwargs
                )
            )

        def _handle_call(self, func, args, kwargs):
            self.calls.append((func, args, kwargs))
            if func not in self.returns:
                return None
            r = self.returns[func].pop(0)
            if len(self.returns[func]) <= 0:
                self.returns.pop(func)
            return r


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core._load_module(
            "openpaperwork_core.config.backend.configparser",
            MockConfigBackendModule()
        )
        self.core.load("openpaperwork_core.cmd.config")
        self.core.init()

        setting = self.core.call_success(
            "config_build_simple", "Global", "WorkDirectory",
            lambda: "file:///home/toto/papers"
        )
        self.core.call_all("config_register", "workdir", setting)

    def test_get_put(self):
        self.core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).returns = {
            'config_backend_put': [None],
            'config_backend_save': [None],
            'config_backend_get': ['file:///pouet/path']
        }

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all("cmd_complete_argparse", cmd_parser)

        args = parser.parse_args(
            ['config', 'put', 'workdir', 'str', 'file:///pouet/path']
        )
        self.core.call_all(
            "cmd_set_console", openpaperwork_core.cmd.DummyConsole()
        )
        r = self.core.call_success(
            "cmd_run", openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                (
                    'config_backend_put',
                    ('Global', "WorkDirectory", "file:///pouet/path"),
                    {}
                ),
                ('config_backend_save', (), {}),
            ]
        )

        args = parser.parse_args(['config', 'get', 'workdir'])
        r = self.core.call_success(
            "cmd_run", openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertEqual(r, {"workdir": "file:///pouet/path"})
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                (
                    'config_backend_put',
                    ('Global', "WorkDirectory", "file:///pouet/path"),
                    {}
                ),
                ('config_backend_save', (), {}),
                # it uses the cache for the get
                # --> no call to config_backend_get
            ]
        )
