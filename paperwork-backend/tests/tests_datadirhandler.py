import shutil
import tempfile
import unittest
import os

import openpaperwork_core


class TestDirHandler(unittest.TestCase):
    def setUp(self):
        self.tmp_paperwork_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_tests"
        )

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)

        class FakeModule:
            __name__ = "fake_module"

            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999999999999

                def paths_get_data_dir(s):
                    return self.core.call_success(
                        "fs_safe", self.tmp_paperwork_dir
                    )

        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.datadirhandler")

        self.core._load_module("fake_module", FakeModule)

        self.core.init()

        self.datadirhandler = self.core.get_by_name(
            "paperwork_backend.datadirhandler"
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_paperwork_dir)

    def test_init(self):
        data_dir_hashed = self.core.call_success(
            "data_dir_handler_get_individual_data_dir")
        self.assertTrue(self.core.call_success("fs_exists", data_dir_hashed))
        self.datadirhandler._delete_old_directories(
            days_to_data_dir_deletion=2)
        # after deleting old directories with the default value,
        # the created directory should still be there
        self.assertTrue(self.core.call_success("fs_exists", data_dir_hashed))
        self.datadirhandler._delete_old_directories(
            days_to_data_dir_deletion=0)
        self.assertFalse(self.core.call_success("fs_exists", data_dir_hashed))

    def test_dir_hash(self):
        data_dir_hashed = self.core.call_success(
            "data_dir_handler_get_individual_data_dir")
        self.assertTrue(self.core.call_success("fs_exists", data_dir_hashed),
                        "directory %s should exist but it does not" % data_dir_hashed)
        workdir = self.core.call_success('storage_get_id')
        self.assertEqual(
            os.path.basename(workdir),
            os.path.basename(data_dir_hashed).split("_")[0]
        )

        data_dir_wo_hash = self.core.call_success("paths_get_data_dir")
        self.assertEqual(os.path.commonprefix(
            [data_dir_wo_hash, data_dir_hashed]
        ), data_dir_wo_hash)

        data_dir_hashed_again = self.core.call_success(
            "data_dir_handler_get_individual_data_dir")
        self.assertEqual(data_dir_hashed, data_dir_hashed_again)
