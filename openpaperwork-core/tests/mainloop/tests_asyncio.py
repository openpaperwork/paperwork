import openpaperwork_core.mainloop.tests
import openpaperwork_core.util


class TestCallback(openpaperwork_core.mainloop.tests.AbstractTestCallback):
    def setUp(self):
        openpaperwork_core.util.reset_singletons()
        super().setUp()

    def get_plugin_name(self):
        return "openpaperwork_core.mainloop.asyncio"


class TestPromise(openpaperwork_core.mainloop.tests.AbstractTestPromise):
    def setUp(self):
        openpaperwork_core.util.reset_singletons()
        super().setUp()

    def get_plugin_name(self):
        return "openpaperwork_core.mainloop.asyncio"
