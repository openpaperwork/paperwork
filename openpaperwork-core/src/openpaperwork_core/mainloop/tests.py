import unittest

from openpaperwork_core.interfaces.mainloop import Mainloop
import openpaperwork_core
import openpaperwork_core.promise


class AbstractTestCallback(unittest.TestCase):
    def get_plugin_name(self):
        """
        Must be overloaded by subclasses
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

        self.val = None

    def test_basic(self):
        def set_val(value):
            self.val = value

        # queue some calls
        self.core.call_all(Mainloop.mainloop_schedule, set_val, 22)
        self.core.call_all(Mainloop.mainloop_quit_graceful)

        self.core.call_one(Mainloop.mainloop)

        self.assertEqual(self.val, 22)


class AbstractTestPromise(unittest.TestCase):
    def get_plugin_name(self):
        """
        Must be overloaded by subclasses
        """
        assert False

    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

        self.alpha_called = False
        self.beta_called = False
        self.stop_called = False
        self.exc_raised = False
        self.idx = 0

    def test_single(self):
        self.stop_called = False

        def stop():
            self.stop_called = True

        p = openpaperwork_core.promise.Promise(self.core, stop)
        p.schedule()
        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)
        self.assertTrue(self.stop_called)

    def test_chain(self):
        self.alpha_called = -1
        self.beta_called = -1
        self.stop_called = -1
        self.idx = 0

        def alpha():
            self.alpha_called = self.idx
            self.idx += 1
            return "alpha"

        def beta(previous):
            self.assertEqual(previous, "alpha")
            self.beta_called = self.idx
            self.idx += 1

        def stop():
            self.stop_called = self.idx
            self.idx += 1

        p = openpaperwork_core.promise.Promise(self.core, alpha)
        p = p.then(beta)
        p = p.then(stop)
        p.schedule()
        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)
        self.assertEqual(self.alpha_called, 0)
        self.assertEqual(self.beta_called, 1)
        self.assertEqual(self.stop_called, 2)

    def test_catch(self):
        self.alpha_called = False
        self.beta_called = False
        self.stop_called = False
        self.exc_raised = False

        def alpha():
            self.alpha_called = True

        def beta():
            self.beta_called = True
            raise Exception("paf")

        def stop():
            self.stop_called = True

        def on_exc(exc):
            self.exc_raised = True

        p = openpaperwork_core.promise.Promise(self.core, alpha)
        p = p.then(beta)
        p = p.then(stop)
        p = p.catch(on_exc)
        p.hide_caught_exceptions = True
        p.schedule()
        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)
        self.assertTrue(self.alpha_called)
        self.assertTrue(self.beta_called)
        self.assertFalse(self.stop_called)
        self.assertTrue(self.exc_raised)
