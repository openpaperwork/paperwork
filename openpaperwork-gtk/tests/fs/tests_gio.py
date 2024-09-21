import openpaperwork_core.tests.local_file


PLUGIN_NAME = "openpaperwork_gtk.fs.gio"


class TestSafe(openpaperwork_core.tests.local_file.AbstractTestSafe):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestUnsafe(openpaperwork_core.tests.local_file.AbstractTestUnsafe):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestOpen(openpaperwork_core.tests.local_file.AbstractTestOpen):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestExists(openpaperwork_core.tests.local_file.AbstractTestExists):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestListDir(openpaperwork_core.tests.local_file.AbstractTestListDir):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestRename(openpaperwork_core.tests.local_file.AbstractTestRename):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestUnlink(openpaperwork_core.tests.local_file.AbstractTestUnlink):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestGetMtime(openpaperwork_core.tests.local_file.AbstractTestGetMtime):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestGetsize(openpaperwork_core.tests.local_file.AbstractTestGetsize):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestIsdir(openpaperwork_core.tests.local_file.AbstractTestIsdir):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestCopy(openpaperwork_core.tests.local_file.AbstractTestCopy):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestMkdirP(openpaperwork_core.tests.local_file.AbstractTestMkdirP):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestTemp(openpaperwork_core.tests.local_file.AbstractTestTemp):
    def get_plugin_name(self):
        return PLUGIN_NAME


class TestResolve(openpaperwork_core.tests.local_file.AbstractTestResolve):
    def get_plugin_name(self):
        return PLUGIN_NAME
