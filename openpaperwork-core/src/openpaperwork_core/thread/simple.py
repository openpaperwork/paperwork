import threading

from . import Task
from .. import PluginBase


class Plugin(PluginBase):
    """
    Simply create a thread for each task to run. Less efficient than a thread
    pool, but may be useful for testing or debugging.
    """
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

    def thread_start(self, func, *args, **kwargs):
        task = Task(self.core, func, args, kwargs)
        thread = threading.Thread(target=task.do)
        thread.daemon = True
        thread.start()
        return True
