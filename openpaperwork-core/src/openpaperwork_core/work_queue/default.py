import logging
import heapq
import threading
import traceback

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.quit import QuitListener
from openpaperwork_core.interfaces.work_queue import WorkQueue
import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Task:
    def __init__(self, work_queue, priority, insert_number, promise):
        self.work_queue = work_queue
        self.priority = priority
        self.insert_number = insert_number
        self.promise = promise
        self.active = True
        self.created_by = traceback.extract_stack()

    def _on_error(self, exc, hide_error):
        if not hide_error:
            LOGGER.error("=== Promise was queued by ===")
            for (idx, stack_el) in enumerate(self.created_by):
                LOGGER.error(
                    "%2d: %20s: L%5d: %s",
                    idx, stack_el[0], stack_el[1], stack_el[2]
                )
        self.work_queue._run_next_promise_locked()
        raise exc

    def __lt__(self, o):
        if self.priority < o.priority:
            return True
        if self.priority > o.priority:
            return False

        if self.insert_number < o.insert_number:
            return True

        return False


class _WorkQueue:
    def __init__(self, name, stop_on_quit, hide_uncatched):
        self.insert_number = 0

        self.name = name
        self.lock = threading.RLock()
        self.queue = []
        self.all_tasks = {}
        self.running = False
        self.stop_on_quit = stop_on_quit
        self.hide_uncatched = hide_uncatched

    def add_promise(self, promise, priority=0):
        self.insert_number += 1

        task = Task(self, -1 * priority, self.insert_number, promise)

        with self.lock:
            heapq.heappush(self.queue, task)
            assert (
                promise not in self.all_tasks or
                not self.all_tasks[promise].active
            )
            self.all_tasks[promise] = task

            if not self.running:
                self._run_next_promise()

    def _run_next_promise(self):
        self.running = True

        try:
            task = None
            while task is None or not task.active:
                task = heapq.heappop(self.queue)
                if task.active:
                    self.all_tasks.pop(task.promise)
        except IndexError:
            self.running = False
            return

        promise = task.promise.then(self._run_next_promise_locked)
        promise.catch(task._on_error, self.hide_uncatched)
        promise.schedule()

    def _run_next_promise_locked(self, *args, **kwargs):
        with self.lock:
            self._run_next_promise()

    def cancel(self, promise):
        try:
            with self.lock:
                task = self.all_tasks[promise]
                task.active = False
        except KeyError:
            LOGGER.debug(
                "Cannot cancel promise [%s]. (already running ?)", promise
            )

    def cancel_all(self):
        # reset the queue
        with self.lock:
            self.queue = []
            self.all_tasks = {}


class Plugin(
    openpaperwork_core.PluginBase,
    WorkQueue,
    QuitListener,
):
    @classmethod
    def get_deps(cls):
        return [
            {
               'interface': Mainloop,
               'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.queues = {}

    def work_queue_create(
            self, queue_name, stop_on_quit=False, hide_uncatched=False):
        LOGGER.debug(
            "Creating work queue [%s] (stop_on_quit=%s)",
            queue_name, stop_on_quit
        )
        self.queues[queue_name] = _WorkQueue(
            queue_name, stop_on_quit, hide_uncatched
        )
        return True

    def work_queue_add_promise(self, queue_name, promise, priority=0):
        if queue_name not in self.queues:
            return None
        self.queues[queue_name].add_promise(promise, priority)
        return True

    def work_queue_cancel(self, queue_name, promise):
        if queue_name not in self.queues:
            return None
        self.queues[queue_name].cancel(promise)
        return True

    def work_queue_cancel_all(self, queue_name):
        if queue_name not in self.queues:
            return None
        self.queues[queue_name].cancel_all()
        return True

    def on_quit(self):
        for queue in self.queues.values():
            if queue.stop_on_quit:
                queue.cancel_all()
