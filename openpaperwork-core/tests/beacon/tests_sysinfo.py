import unittest

import openpaperwork_core


class TestSysinfo(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

        class FakeAppModule:
            __name__ = "fake_app"

            class Plugin(openpaperwork_core.PluginBase):
                @classmethod
                def get_interfaces(cls):
                    return ['app']

                def app_get_name(self):
                    return "Paperwork"

                def app_get_fs_name(self):
                    return "paperwork2"

                def app_get_version(self):
                    return "2.1"

        self.core._load_module("fake_app", FakeAppModule())
        self.core.load("openpaperwork_core.beacon.sysinfo")
        self.core.init()

    def test_get(self):
        # just go through the code to make sure it actually runs correctly
        # (we cannot check the output since it's system-dependant)
        out = {}
        self.core.call_all("stats_get", out)
        self.assertIn('os_name', out)
        self.assertIn('platform_architecture', out)
        self.assertIn('platform_processor', out)
        self.assertIn('platform_distribution', out)
        self.assertIn('cpu_count', out)
