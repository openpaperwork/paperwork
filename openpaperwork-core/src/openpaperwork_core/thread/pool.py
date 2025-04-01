import logging
import multiprocessing
import queue
import threading

from . import Task
from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Thread(threading.Thread):
    def __init__(self, plugin, thread_id):
        super().__init__(name="paperwork_thread_{}".format(thread_id))
        self.daemon = True
        self.task_queue = plugin.queue
        self.core = plugin.core
        self.running = True

    def run(self):
        LOGGER.info("Thread %s ready", self.name)
        while True:
            task = self.task_queue.get()
            if task is None:
                break
            task.do()
        LOGGER.info("Thread %s stopped", self.name)


class Plugin(PluginBase):
    def __init__(self, core):
        super().__init__(core)
        self.queue = queue.Queue()
        self.pool = None

    @classmethod
    def get_interfaces(cls):
        return ['thread']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def on_mainloop_start(self):
        if self.pool is None:
            self.pool = [
                Thread(self, x)
                for x in range(0, max(4, multiprocessing.cpu_count()))
            ]
            for t in self.pool:
                t.start()

    def on_mainloop_quit(self):
        if self.pool is not None:
            for t in self.pool:
                self.queue.put(None)
            # in case the mainloop is restarted later:
            self.queue = queue.Queue()
            self.pool = None

    def thread_start(self, func, *args, **kwargs):
        if self.pool is None:
            self.on_mainloop_start()
        task = Task(self.core, func, args, kwargs)
        self.queue.put(task)
