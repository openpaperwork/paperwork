import threading
import unittest

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.mainloop import MainloopListener
from openpaperwork_core.interfaces.thread import ThreadManager
import openpaperwork_core


class AbstractTestThread(unittest.TestCase):
    def get_plugin_name(self):
        """
        Must be overloaded by subclasses
        """
        assert False

    def setUp(self):
        class DummyMainloop:
            __name__ = "dummy_mainloop"

            class Plugin(openpaperwork_core.PluginBase, Mainloop):
                def mainloop(s, halt_on_uncaught_exception=True, log_uncaught=True):
                    pass

                def mainloop_get_thread_id(s):
                    pass

                def mainloop_quit_graceful(s):
                    pass

                def mainloop_quit_now(s):
                    pass

                def mainloop_schedule(s, func, *args, delay_s=0, **kwargs):
                    pass

                def mainloop_execute(s, func, *args, **kwargs):
                    pass

                def mainloop_ref(s, r):
                    pass

                def mainloop_unref(s, r):
                    pass

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("dummy_mainloop", DummyMainloop())
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_basic(self):
        out = {
            'task_a_done': False,
            'task_b_done': False,
        }
        sem = threading.Semaphore(value=0)

        def task_a():
            out['task_a_done'] = True
            sem.release()

        def task_b():
            out['task_b_done'] = True
            sem.release()

        self.core.call_all(MainloopListener.on_mainloop_start)

        self.core.call_one(ThreadManager.thread_start, task_a)
        self.core.call_one(ThreadManager.thread_start, task_b)

        for _ in range(0, 2):
            sem.acquire()

        self.assertTrue(out['task_a_done'])
        self.assertTrue(out['task_b_done'])

        self.core.call_all(MainloopListener.on_mainloop_quit)

    def test_mainloop_restart(self):
        # mainloop can be stopped and started again many times
        out = {}
        sem = threading.Semaphore(value=0)

        def task_a():
            out['task_a_done'] = True
            sem.release()

        out['task_a_done'] = False
        self.core.call_all(MainloopListener.on_mainloop_start)
        self.core.call_one(ThreadManager.thread_start, task_a)
        for _ in range(0, 1):
            sem.acquire()
        self.assertTrue(out['task_a_done'])
        self.core.call_all(MainloopListener.on_mainloop_quit)

        out['task_a_done'] = False
        self.core.call_all(MainloopListener.on_mainloop_start)
        self.core.call_one(ThreadManager.thread_start, task_a)
        for _ in range(0, 1):
            sem.acquire()
        self.assertTrue(out['task_a_done'])
        self.core.call_all(MainloopListener.on_mainloop_quit)
