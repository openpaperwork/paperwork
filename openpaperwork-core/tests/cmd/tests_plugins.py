import argparse
import os
import tempfile
import unittest

from openpaperwork_core.interfaces.app import App
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core
import openpaperwork_core.cmd


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

        self.config_path = tempfile.NamedTemporaryFile(delete=False)
        self.config_path.close()

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("app", FakeAppModule())  # type: ignore
        self.core.load(
            'openpaperwork_core.config.backend.configparser',
            config_path="file://" + self.config_path.name
        )
        self.core.load("openpaperwork_core.cmd.plugins")
        self.core.load = lambda *args, **kwargs: None
        self.core.init()

        setting = self.core.call_success(
            Config.config_build_simple, "Global", "WorkDirectory",
            lambda: "file:///home/toto/papers"
        )
        self.core.call_all(Config.config_register, "workdir", setting)

    def tearDown(self):
        os.unlink(self.config_path.name)

    def test_add_remove_list_plugin(self):
        self.core.call_all(Config.config_load)
        self.core.call_all(
            Config.config_load_plugins, 'paperwork-shell', default_plugins=['pouet']
        )

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all(Shell.cmd_complete_argparse, cmd_parser)

        self.core.call_all(
            Shell.cmd_set_console, openpaperwork_core.cmd.DummyConsole()
        )
        args = parser.parse_args(
            ['plugins', 'add', 'plugin_a', '--no_auto']
        )
        r = self.core.call_success(
            Shell.cmd_run, openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)
        args = parser.parse_args(
            ['plugins', 'add', 'plugin_b', '--no_auto']
        )
        r = self.core.call_success(
            Shell.cmd_run, openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)
        args = parser.parse_args(
            ['plugins', 'add', 'plugin_c', '--no_auto']
        )
        r = self.core.call_success(
            Shell.cmd_run, openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)

        args = parser.parse_args(['plugins', 'list'])
        r = self.core.call_success(
            Shell.cmd_run, openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertEqual(
            sorted(r), ['plugin_a', 'plugin_b', 'plugin_c', 'pouet']
        )

        args = parser.parse_args(
            ['plugins', 'remove', 'plugin_b', '--no_auto']
        )
        r = self.core.call_success(
            Shell.cmd_run, openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)

        args = parser.parse_args(['plugins', 'list'])
        r = self.core.call_success(
            Shell.cmd_run, openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertEqual(sorted(r), ['plugin_a', 'plugin_c', 'pouet'])
