#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

import os
from Queue import Queue
import sys
import threading
import time
import traceback

from gi.repository import GObject


class _WorkerThread(object):
    def __init__(self):
        self.__must_stop = False
        self.__todo = Queue()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def run(self):
        print "Workers: Worker thread started"

        while True:
            (worker, kwargs) = self.__todo.get()
            if worker is None:
                print "Workers: Worker thread halting"
                return
            try:
                worker._wrapper(**kwargs)
            except Exception, exc:
                print ("Worker [%s] raised an exception: %s"
                       % (worker.name, str(exc)))
                traceback.print_exc(file=sys.stdout)
            self.__todo.task_done()

        print "Workers: Worker thread stopped"

    def queue_worker(self, worker, kwargs):
        print "Workers: Queueing [%s]" % (worker.name)
        self.__todo.put((worker, kwargs))

    def halt(self):
        print "Workers: Requesting halt"
        self.__todo.put((None, None))

    def wait(self):
        """
        Wait for all the pending workers to end
        """
        self.__todo.join()


_WORKER_THREAD = _WorkerThread()


def halt():
    _WORKER_THREAD.halt()


class BasicWorker(GObject.GObject):
    can_interrupt = False

    def __init__(self, name):
        GObject.GObject.__init__(self)
        self.name = name
        self.can_run = True
        self.is_running = False
        self.__started_by = None

    def do(self, **kwargs):
        # implemented by the child class
        #
        # if can_interrupt = True, the child class must check self.can_run as
        # often as possible
        assert()

    def _wrapper(self, **kwargs):
        if not self.can_run:
            return
        self.is_running = True
        print "Workers: [%s] started" % (self.name)
        try:
            self.do(**kwargs)
        finally:
            self.is_running = False
            self.__started_by = None
            print "Workers: [%s] ended" % (self.name)

    def start(self, **kwargs):
        if self.is_running and self.can_run:
            print "====="
            print "ERROR"
            print "Thread '%s' was already started by:" % (self.name)
            idx = 0
            for stack_el in self.__started_by:
                print ("%2d : %20s : L%5d : %s"
                       % (idx, os.path.basename(stack_el[0]),
                          stack_el[1], stack_el[2]))
                idx += 1
            print "====="
            raise threading.ThreadError(
                ("Tried to start a thread already running: %s"
                 % (self.name)))
        self.__started_by = traceback.extract_stack()
        self.can_run = True

    def soft_stop(self):
        print "Stopping worker [%s]" % (self)
        if not self.can_interrupt and self.is_running:
            print ("Trying to stop worker [%s], but it cannot be stopped"
                   % (self.name))
        self.can_run = False


class Worker(BasicWorker):
    def __init__(self, name):
        BasicWorker.__init__(self, name)

    def start(self, **kwargs):
        global _WORKER_THREAD
        BasicWorker.start(self)
        _WORKER_THREAD.queue_worker(self, kwargs)

    def stop(self):
        global _WORKER_THREAD
        self.soft_stop()
        # Sadly, it seems there is no nice way for us to wait for all
        # the instances of our worker to end. We can only wait for
        # all the workers to end
        _WORKER_THREAD.wait()

    def wait(self):
        global _WORKER_THREAD

        if not self.is_running:
            return

        # Sadly, it seems there is no nice way for us to wait for all
        # the instances of our worker to end. We can only wait for
        # all the workers to end
        _WORKER_THREAD.wait()

    def __str__(self):
        return self.name


class IndependantWorker(BasicWorker):
    def __init__(self, name):
        BasicWorker.__init__(self, name)
        self.thread = None

    def start(self, **kwargs):
        BasicWorker.start(self)

        self.thread = threading.Thread(target=self._wrapper, kwargs=kwargs)
        self.thread.start()

    def stop(self):
        print "Stopping worker [%s]" % (self)
        self.soft_stop()
        self.wait()

    def wait(self):
        if not self.is_running:
            return

        if self.thread is not None and self.thread.is_alive():
            self.thread.join()
            assert(not self.is_running)

    def __str__(self):
        return self.name


class WorkerQueue(Worker):
    can_interrupt = True

    __gsignals__ = {
        'queue-start' : (GObject.SignalFlags.RUN_LAST, None, ()),
        'queue-stop' : (GObject.SignalFlags.RUN_LAST, None,
                        # Arg: Exception raised by a worker, None if none
                        (GObject.TYPE_PYOBJECT, )),
    }
    local_signals = ['queue-start', 'queue-stop']

    def __init__(self, name):
        Worker.__init__(self, name)
        self.__queue = []
        self.__current_worker = None
        self.__signals = {}

    def add_worker(self, worker):
        for (signal, (handler, kargs)) in self.__signals.iteritems():
            worker.connect(signal, handler, *kargs)
        self.__queue.append(worker)

    def do(self, **kwargs):
        self.emit('queue-start')
        exception = None
        try:
            try:
                while len(self.__queue) > 0 and self.can_run:
                    self.__current_worker = self.__queue.pop(0)
                    print ("Queue [%s]: Starting worker [%s]"
                           % (self.name, self.__current_worker.name))
                    self.__current_worker.do(**kwargs)
                    print ("Queue [%s]: Worker [%s] has ended"
                           % (self.name, self.__current_worker.name))
            except Exception, exc:
                exception = exc
                raise
        finally:
            self.__current_worker = None
            self.emit('queue-stop', exception)

    def connect(self, signal, handler, *kargs):
        if signal in self.local_signals:
            Worker.connect(self, signal, handler, *kargs)
            return
        self.__signals[signal] = (handler, kargs)
        for worker in self.__queue:
            worker.connect(signal, handler, *kargs)

    def stop(self):
        if self.__current_worker != None:
            self.__current_worker.stop()
        Worker.stop(self)

GObject.type_register(WorkerQueue)


class WorkerProgressUpdater(IndependantWorker):
    """
    Update a progress bar a predefined timing.
    """

    can_interrupt = True

    NB_UPDATES = 50

    def __init__(self, name, progressbar):
        self.name = "Progress bar updater: %s" % (name)
        IndependantWorker.__init__(self, self.name)
        self.progressbar = progressbar

    def do(self, value_min=0.0, value_max=0.5, total_time=20.0):
        for upd in range(0, self.NB_UPDATES):
            if not self.can_run:
                return
            val = value_max - value_min
            val *= upd
            val /= self.NB_UPDATES
            val += value_min

            GObject.idle_add(self.progressbar.set_fraction, val)
            time.sleep(total_time / self.NB_UPDATES)


GObject.type_register(WorkerProgressUpdater)
