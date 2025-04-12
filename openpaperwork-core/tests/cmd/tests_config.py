import argparse
import unittest

from openpaperwork_core.interfaces.app import App
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.config_backend import ConfigBackend
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core
import openpaperwork_core.cmd


class MockConfigBackendModule:
    """
    Plugin paperwork_backend.config uses openpaperwork.config_file.
    This mock mocks openpaperwork.config_file so we can test
    paperwork_backend.config.file
    """
    __name__ = "openpaperwork_core.config.backend.configparser"

    class Plugin(
        openpaperwork_core.PluginBase,
        ConfigBackend,
    ):
        def __init__(self, core):
            super().__init__(core)
            self.calls = []
            self.returns = {}

        def config_backend_load(self, *args, **kwargs):
            self._handle_call('config_backend_load', args, kwargs)

        def config_backend_save(self, *args, **kwargs):
            self._handle_call('config_backend_save', args, kwargs)

        def config_backend_load_plugins(self, *args, **kwargs):
            self._handle_call('config_backend_load_plugins', args, kwargs)

        def config_backend_add_plugin(self, *args, **kwargs):
            self._handle_call('config_backend_add_plugin', args, kwargs)

        def config_backend_remove_plugin(self, *args, **kwargs):
            self._handle_call('config_backend_remove_plugin', args, kwargs)

        def config_backend_put(self, *args, **kwargs):
            self._handle_call('config_backend_put', args, kwargs)

        def config_backend_get(self, *args, **kwargs):
            self._handle_call('config_backend_get', args, kwargs)

        def config_backend_add_observer(self, *args, **kwargs):
            self._handle_call('config_backend_add_observer', args, kwargs)

        def config_backend_remove_observer(self, *args, **kwargs):
            self._handle_call(
                'config_backend_remove_observer', args, kwargs
            )

        def config_backend_list_active_plugins(self, *args, **kwargs):
            self._handle_call(
                'config_backend_list_active_plugins', args, kwargs
            )

        def config_backend_del(self, *args, **kwargs):
            raise NotImplementedError()

        def config_backend_reset_plugins(self, *args, **kwargs):
            raise NotImplementedError()

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
        class FakeAppModule:
            __name__ = "fake_app"

            class Plugin(
                    openpaperwork_core.PluginBase,
                    App,
            ):
                def app_get_name(self):
                    return "Paperwork"

                def app_get_fs_name(self):
                    return "paperwork2"

                def app_get_version(self):
                    return "2.1"

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("fake_app", FakeAppModule())  # type: ignore
        self.core.load(
            "openpaperwork_core.config.backend.configparser",
            MockConfigBackendModule()
        )
        self.core.load("openpaperwork_core.cmd.config")
        self.core.init()

        setting = self.core.call_success(
            Config.config_build_simple, "Global", "WorkDirectory",
            lambda: "file:///home/toto/papers"
        )
        self.core.call_all(Config.config_register, "workdir", setting)

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
        self.core.call_all(Shell.cmd_complete_argparse, cmd_parser)

        args = parser.parse_args(
            ['config', 'put', 'workdir', 'str', 'file:///pouet/path']
        )
        self.core.call_all(
            Shell.cmd_set_console, openpaperwork_core.cmd.DummyConsole()
        )
        r = self.core.call_success(
            Shell.cmd_run, openpaperwork_core.cmd.DummyConsole(), args
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
            Shell.cmd_run, openpaperwork_core.cmd.DummyConsole(), args
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
