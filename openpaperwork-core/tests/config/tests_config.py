import unittest

from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.config_backend import ConfigBackend
import openpaperwork_core


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
            self.rets = {}

        def config_backend_load(self, *args, **kwargs):
            return self._handle_call('config_backend_load', args, kwargs)

        def config_backend_save(self, *args, **kwargs):
            return self._handle_call('config_backend_save', args, kwargs)

        def config_backend_load_plugins(self, *args, **kwargs):
            return self._handle_call('config_backend_load_plugins', args, kwargs)

        def config_backend_add_plugin(self, *args, **kwargs):
            return self._handle_call('config_backend_add_plugin', args, kwargs)

        def config_backend_remove_plugin(self, *args, **kwargs):
            return self._handle_call('config_backend_remove_plugin', args, kwargs)

        def config_backend_put(self, *args, **kwargs):
            return self._handle_call('config_backend_put', args, kwargs)

        def config_backend_get(self, *args, **kwargs):
            return self._handle_call('config_backend_get', args, kwargs)

        def config_backend_add_observer(self, *args, **kwargs):
            return self._handle_call('config_backend_add_observer', args, kwargs)

        def config_backend_remove_observer(self, *args, **kwargs):
            return self._handle_call('config_backend_remove_observer', args, kwargs)

        def config_backend_del(self, *args, **kwargs):
            raise NotImplementedError()

        def config_backend_list_active_plugins(self, *args, **kwargs):
            raise NotImplementedError()

        def config_backend_reset_plugins(self, *args, **kwargs):
            raise NotImplementedError()

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
        self.core.load(
            "openpaperwork_core.config.backend.configparser",
            MockConfigBackendModule()  # type: ignore
        )
        self.core.load("openpaperwork_core.config")
        self.core.init()

        setting = self.core.call_success(
            Config.config_build_simple, "Global", "WorkDirectory",
            lambda: "file:///home/toto/papers"
        )
        self.core.call_all(Config.config_register, "workdir", setting)

    def test_config_load(self):
        self.core.call_all(Config.config_load)
        self.core.call_all(
            Config.config_load_plugins, 'some_plugin_list_name',
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
        default = self.core.call_success(Config.config_get, "workdir")
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
            Config.config_get, "workdir"
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

        val1 = self.core.call_success(Config.config_get, "workdir")
        val2 = self.core.call_success(Config.config_get, "workdir")
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
