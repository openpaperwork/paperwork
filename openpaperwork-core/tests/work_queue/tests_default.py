import unittest

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.work_queue import WorkQueue
import openpaperwork_core


class TestQueue(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.work_queue.default")
        self.core.init()

    def test_single_task(self):
        self.task_done = False

        def do_task():
            self.task_done = True

        self.core.call_all(WorkQueue.work_queue_create, "some_work_queue")
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task)
        )

        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)

        self.assertTrue(self.task_done)

    def test_many_tasks(self):
        self.task_a_done = False
        self.task_b_done = False

        def do_task_a():
            self.assertFalse(self.task_a_done)
            self.assertFalse(self.task_b_done)
            self.task_a_done = True

        def do_task_b():
            self.assertTrue(self.task_a_done)
            self.assertFalse(self.task_b_done)
            self.task_b_done = True

        self.core.call_all(WorkQueue.work_queue_create, "some_work_queue")
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_a)
        )
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_b)
        )

        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)

        self.assertTrue(self.task_a_done)
        self.assertTrue(self.task_b_done)

    def test_uncaught(self):
        # make sure the work queue doesn't stop if an exception is raised
        # by one of the task/promise.
        self.task_a_done = False
        self.task_b_done = False

        def do_task_a():
            self.assertFalse(self.task_a_done)
            self.assertFalse(self.task_b_done)
            self.task_a_done = True
            raise Exception("Test exception. May be normal. Do not panic :-)")

        def do_task_b():
            self.assertTrue(self.task_a_done)
            self.assertFalse(self.task_b_done)
            self.task_b_done = True

        self.core.call_all(
            WorkQueue.work_queue_create, "some_work_queue", hide_uncatched=True
        )
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(
                self.core, do_task_a,
                hide_caught_exceptions=True
            )
        )
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_b)
        )

        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(
            Mainloop.mainloop,
            halt_on_uncaught_exception=False, log_uncaught=False
        )

        self.assertTrue(self.task_a_done)
        self.assertTrue(self.task_b_done)

    def test_cancel_all(self):
        self.task_a_done = False
        self.task_b_done = False

        def do_task_a():
            self.assertFalse(self.task_a_done)
            self.assertFalse(self.task_b_done)
            self.task_a_done = True
            return "some_crap"

        def do_task_b():
            self.assertTrue(self.task_a_done)
            self.assertFalse(self.task_b_done)
            self.task_b_done = True
            self.core.call_all(WorkQueue.work_queue_cancel_all, "some_work_queue")

        def do_task_c():
            self.assertTrue(False)

        self.core.call_all(WorkQueue.work_queue_create, "some_work_queue")
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_a)
        )
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_b)
        )
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_c)
        )

        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)

        self.assertTrue(self.task_a_done)
        self.assertTrue(self.task_b_done)

    def test_cancel(self):
        self.task_a_done = False
        self.task_b_done = False
        self.task_d_done = False

        def do_task_a():
            self.assertFalse(self.task_a_done)
            self.assertFalse(self.task_b_done)
            self.task_a_done = True
            return "some_crap"

        def do_task_b():
            self.assertTrue(self.task_a_done)
            self.assertFalse(self.task_b_done)
            self.task_b_done = True
            self.core.call_all(
                WorkQueue.work_queue_cancel, "some_work_queue", task_c
            )

        def do_task_c():
            self.assertTrue(False)

        def do_task_d():
            self.assertTrue(self.task_a_done)
            self.assertTrue(self.task_b_done)
            self.task_d_done = True
            return "some_crap"

        task_c = openpaperwork_core.promise.Promise(self.core, do_task_c)

        self.core.call_all(WorkQueue.work_queue_create, "some_work_queue")
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_a)
        )
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_b)
        )
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            task_c
        )
        self.core.call_one(
            WorkQueue.work_queue_add_promise, "some_work_queue",
            openpaperwork_core.promise.Promise(self.core, do_task_d)
        )

        self.core.call_all(Mainloop.mainloop_quit_graceful)
        self.core.call_one(Mainloop.mainloop)

        self.assertTrue(self.task_a_done)
        self.assertTrue(self.task_b_done)
        self.assertTrue(self.task_d_done)
