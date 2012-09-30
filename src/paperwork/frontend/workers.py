import sys
import threading
import time

import gobject

class Worker(gobject.GObject):
    can_interrupt = False

    def __init__(self, name):
        gobject.GObject.__init__(self)
        self.name = name
        self.can_run = True
        self.__thread = None

    def do(self, **kwargs):
        # implemented by the child class
        #
        # if can_interrupt = True, the child class must check self.can_run as
        # often as possible
        assert()

    def __wrapper(self, **kwargs):
        print "Workers: [%s] started" % (self.name)
        self.do(**kwargs)
        print "Workers: [%s] ended" % (self.name)

    def start(self, **kwargs):
        if self.is_running:
            raise threading.ThreadError(
                ("Tried to start a thread already running: %s"
                 % (self.name)))
        self.can_run = True
        self.__thread = threading.Thread(target=self.__wrapper, kwargs=kwargs)
        self.__thread.start()

    def stop(self):
        if not self.is_running:
            return
        print "Stopping worker [%s]" % (self)
        sys.stdout.flush()
        if not self.can_interrupt:
            print ("Trying to stop worker [%s], but it cannot be stopped"
                   % (self.name))
        self.can_run = False
        if self.__thread.is_alive():
            self.__thread.join()

    def wait(self):
        self.__thread.join()

    def __get_is_running(self):
        return (self.__thread != None and self.__thread.is_alive())

    is_running = property(__get_is_running)

    def __str__(self):
        return self.name


class WorkerQueue(Worker):
    can_interrupt = True

    __gsignals__ = {
        'queue-start' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'queue-stop' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                        # Arg: Exception raised by a worker, None if none
                        (gobject.TYPE_PYOBJECT, )),
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

gobject.type_register(WorkerQueue)


class WorkerProgressUpdater(Worker):
    """
    Update a progress bar a predefined timing.
    """

    can_interrupt = True

    NB_UPDATES = 50

    def __init__(self, name, progressbar):
        self.name = "Progress bar updater: %s" % (name)
        Worker.__init__(self, self.name)
        self.progressbar = progressbar

    def do(self, value_min=0.0, value_max=0.5, total_time=20.0):
        for upd in range(0, self.NB_UPDATES):
            if not self.can_run:
                return
            val = value_max - value_min
            val *= upd
            val /= self.NB_UPDATES
            val += value_min

            gobject.idle_add(self.progressbar.set_fraction, val)
            time.sleep(total_time / self.NB_UPDATES)


gobject.type_register(WorkerProgressUpdater)
