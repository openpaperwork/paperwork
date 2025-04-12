from typing import Dict
from typing import List
import logging
import threading
import traceback

from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.thread import ThreadManager


LOGGER = logging.getLogger(__name__)


def get_deps() -> List[Dict]:
    return [
        {
            "interface": Mainloop,
            "defaults": ["openpaperwork_core.mainloop.asyncio"],
        },
        {
            "interface": ThreadManager,
            "defaults": ["openpaperwork_core.thread.simple"],
        },
    ]


class BasePromise:
    def __init__(
                self, core, func=None, args=None, kwargs=None, parent=None,
                hide_caught_exceptions=False
            ):
        # we allow dummy Promise with not function provided. It allows to
        # write cleaner code in some cases.
        self.core = core
        self.func = func
        self.hide_caught_exceptions = hide_caught_exceptions
        if args is None:
            self.args = ()
        else:
            self.args = args
        if kwargs is None:
            self.kwargs = {}
        else:
            self.kwargs = kwargs
        self.parent = parent

        self._then = []
        self._catch = []

        self.scheduled = False

        self.parent_promise_return = None
        self.created_by = traceback.extract_stack()

    def __str__(self):
        return "Promise<{}>({})".format(str(self.func), id(self))

    def __repr__(self):
        return str(self)

    def then(self, callback, *args, **kwargs):
        if isinstance(callback, BasePromise):
            assert args is None or len(args) <= 0
            assert kwargs is None or len(kwargs) <= 0
            last_promise = callback
            while callback.parent is not None:
                callback = callback.parent
            next_promise = callback
            next_promise.parent = self
        else:
            next_promise = Promise(
                self.core, callback, args, kwargs, parent=self
            )
            last_promise = next_promise
        if not next_promise.hide_caught_exceptions:
            next_promise.hide_caught_exceptions = self.hide_caught_exceptions
        self._then.append(next_promise)
        return last_promise

    def catch(self, callback, *args, **kwargs):
        self._catch.append((callback, args, kwargs))
        return self

    def on_error(self, exc, hide_caught_exceptions=False):
        self.scheduled = False
        hide_caught_exceptions = (
            hide_caught_exceptions or self.hide_caught_exceptions
        )
        if len(self._catch) > 0:
            if hide_caught_exceptions:
                trace = lambda *args, **kwargs: None  # NOQA: E731
            else:
                trace = LOGGER.warning
            caught = "caught"
        elif len(self._then) > 0:
            for t in self._then:
                t.scheduled = False
                t.on_error(exc, hide_caught_exceptions)
            return
        else:
            trace = LOGGER.error
            caught = "uncaught"

        trace("=== %s exception in promise ===", caught, exc_info=exc)
        trace("promise.func=%s", self.func)
        trace("promise.args=%s", self.args)
        trace("promise.kwargs=%s", self.kwargs)
        trace("promise.parent=%s", self.parent)
        trace(
            "promise.parent_promise_return=%s", self.parent_promise_return
        )
        trace("=== Promise was created by ===")
        for (idx, stack_el) in enumerate(self.created_by):
            trace(
                "%2d: %20s: L%5d: %s",
                idx, stack_el[0], stack_el[1], stack_el[2]
            )

        if len(self._catch) > 0:
            for (c, args, kwargs) in self._catch:
                self.core.call_one(
                    Mainloop.mainloop_schedule, c, exc, *args, **kwargs
                )
            return

        raise exc

    def _do(self, args):
        try:
            self.do(args)
        finally:
            self.scheduled = False

    def schedule(self, *args):
        scheduled = self.scheduled

        s = self
        while s.parent is not None:
            scheduled = scheduled or s.scheduled
            s.scheduled = True
            s = s.parent
        s.scheduled = True

        if scheduled:
            # a parent promise already scheduled --> we made sure to mark
            # all the children promises as scheduled, but there is no
            # need to actually schedule the parent.
            return

        if args == ():
            args = None
        self.core.call_one(Mainloop.mainloop_schedule, s._do, args)

    def wait(self):
        assert (
            # must never be called from main loop.
            threading.current_thread().ident !=
            self.core.call_success(Mainloop.mainloop_get_thread_id)
        )
        event = threading.Event()
        out = None

        def wakeup(r=None):
            nonlocal out
            out = r

        self.then(event.set)
        event.wait()
        return out


class Promise(BasePromise):
    """
    Executed in the main loop thread.
    Requires a plugin implementing the interface 'mainloop'.
    """

    def do(self, parent_r=None):
        self.parent_promise_return = parent_r
        try:
            if self.func is None:
                our_r = None
            else:
                if parent_r is None:
                    args = self.args
                else:
                    args = (parent_r,) + self.args

                LOGGER.debug(
                    "Promise: Begin: %s(%s, %s)", self.func, args, self.kwargs
                )
                our_r = self.func(*args, **self.kwargs)
                LOGGER.debug(
                    "Promise: End: %s(%s, %s)", self.func, args, self.kwargs
                )

            for t in self._then:
                self.core.call_one(Mainloop.mainloop_schedule, t._do, our_r)
        except Exception as exc:
            self.on_error(exc)


class DelayPromise(BasePromise):
    """
    Promise adding delay between 2 other promises.
    Requires a plugin implementing the interface 'mainloop'
    """
    def __init__(self, core, delay_s):
        super().__init__(core)
        self.delay_s = delay_s

    def __str__(self):
        return "DelayPromise<delay_s={}>({})".format(self.delay_s, id(self))

    def _call_then(self, parent_r):
        for t in self._then:
            self.core.call_one(Mainloop.mainloop_schedule, t._do, parent_r)

    def do(self, parent_r=None):
        LOGGER.debug("Promise: delay: %fs", self.delay_s)
        self.core.call_one(
            Mainloop.mainloop_schedule, self._call_then, parent_r,
            delay_s=self.delay_s
        )


class ThreadedPromise(BasePromise):
    """
    Promise for which the provided callback will be run in another thread,
    leaving the main loop thread free to do other things.
    Requires a plugin implementing the interface 'mainloop' and a plugin
    implementing the interface 'thread'.

    IMPORTANT: This should ONLY be used for long-lasting tasks that cannot
    be split in small tasks (image processing, OCR, etc). The callback provided
    must be really careful regarding thread-safety.
    """

    def __str__(self):
        return "ThreadedPromise<{}>({})".format(str(self.func), id(self))

    def _threaded_do(self, parent_r):
        try:
            if parent_r is None:
                args = self.args
            else:
                args = (parent_r,) + self.args

            LOGGER.debug(
                "Threaded promise: Begin: %s(%s, %s)",
                self.func, args, self.kwargs
            )
            our_r = self.func(*args, **self.kwargs)
            LOGGER.debug(
                "Threaded promise: end: %s(%s, %s)",
                self.func, args, self.kwargs
            )

            for t in self._then:
                self.core.call_one(Mainloop.mainloop_schedule, t._do, our_r)
        except Exception as exc:
            self.core.call_one(Mainloop.mainloop_schedule, self.on_error, exc)

    def do(self, parent_r=None):
        self.parent_promise_return = parent_r
        try:
            if self.func is None:
                # no thread, we immediately schedule the next promises
                for t in self._then:
                    self.core.call_one(Mainloop.mainloop_schedule, t._do, None)
                return

            self.core.call_one(ThreadManager.thread_start, self._threaded_do, parent_r)
        except Exception as exc:
            self.on_error(exc)
            return
