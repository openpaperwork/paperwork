import unittest

import openpaperwork_core


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
            self.rets = {}
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

        def _handle_call(self, func, args, kwargs):
            self.calls.append((func, args, kwargs))
            if func not in self.rets:
                return None
            r = self.rets[func].pop(0)
            if len(self.rets[func]) <= 0:
                self.rets.pop(func)
            return r


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core._load_module(
            "openpaperwork_core.config.backend.configparser",
            MockConfigBackendModule()
        )
        self.core.load("openpaperwork_core.config")
        self.core.init()

        setting = self.core.call_success(
            "config_build_simple", "Global", "WorkDirectory",
            lambda: "file:///home/toto/papers"
        )
        self.core.call_all("config_register", "workdir", setting)

    def test_config_load(self):
        self.core.call_all('config_load')
        self.core.call_all(
            'config_load_plugins', 'some_plugin_list_name',
            default_plugins=['pouet']
        )
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                ('config_backend_load', ('openpaperwork_core',), {}),
                (
                    'config_backend_load_plugins',
                    ('some_plugin_list_name', ['pouet'],), {}
                ),
            ]
        )

    def test_get_default(self):
        default = self.core.call_success("config_get", "workdir")
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                ('config_backend_get', ('Global', "WorkDirectory", None), {}),
            ]
        )
        self.assertEqual(default, "file:///home/toto/papers")

    def test_get_nondefault(self):
        self.core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).rets = {
            'config_backend_get': ['file:///pouet/path']
        }

        val = self.core.call_success(
            "config_get", "workdir"
        )
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                ('config_backend_get', ('Global', "WorkDirectory", None), {}),
            ]
        )
        self.assertEqual(val, "file:///pouet/path")

    def test_get_cache(self):
        self.core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).rets = {
            # only one call expected
            'config_backend_get': ['file:///pouet/path']
        }

        val1 = self.core.call_success("config_get", "workdir")
        val2 = self.core.call_success("config_get", "workdir")
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                ('config_backend_get', ('Global', "WorkDirectory", None), {}),
            ]
        )
        self.assertEqual(val1, "file:///pouet/path")
        self.assertEqual(val1, val2)
