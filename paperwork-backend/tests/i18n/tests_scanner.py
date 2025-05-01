import unittest

import openpaperwork_core

from paperwork_backend.interfaces.i18n_scanner import I18nScanner


class TestScannerI18n(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.i18n.scanner")
        self.core.init()

        plugin = self.core.get_by_name("paperwork_backend.i18n.scanner")
        plugin.keywords = {
            "centrally": "CENTRALLY",
            "feeder": "FEEDER",
            "flatbed": "FLATBED",
            "left aligned": "LEFT ALIGNED",
        }

    def test_i18n_source(self):
        self.assertEqual(
            self.core.call_success(I18nScanner.i18n_scanner_source, "flatbed"), "FLATBED"
        )
        self.assertEqual(
            self.core.call_success(I18nScanner.i18n_scanner_source, "fEEder"), "FEEDER"
        )
        self.assertEqual(
            self.core.call_success(I18nScanner.i18n_scanner_source, "feeder toto"),
            "FEEDER toto"
        )
        self.assertEqual(
            self.core.call_success(I18nScanner.i18n_scanner_source, "toto feeder"),
            "toto FEEDER"
        )
        self.assertEqual(
            self.core.call_success(
                # Brother MFC-7360N + Linux (Sane)
                I18nScanner.i18n_scanner_source, "feeder(centrally aligned)"
            ),
            "FEEDER(CENTRALLY aligned)"
        )
        self.assertEqual(
            self.core.call_success(
                # Brother MFC-7360N + Linux (Sane)
                I18nScanner.i18n_scanner_source, "feeder(left aligned)"
            ),
            "FEEDER(LEFT ALIGNED)"
        )
