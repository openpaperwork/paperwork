import threading

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.thread import ThreadManager
import openpaperwork_core
import openpaperwork_core.thread


class Plugin(
    openpaperwork_core.PluginBase,
    ThreadManager,
):
    """
    Simply create a thread for each task to run. Less efficient than a thread
    pool, but may be useful for testing or debugging.
    """
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': Mainloop,
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def thread_start(self, func, *args, **kwargs):
        task = openpaperwork_core.thread.Task(self.core, func, args, kwargs)
        thread = threading.Thread(target=task.do)
        thread.daemon = True
        thread.start()
        return True
