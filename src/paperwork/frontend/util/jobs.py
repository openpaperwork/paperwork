#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
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

import heapq
import logging
import itertools
import sys
import threading
import traceback
import time

from gi.repository import GLib
from gi.repository import GObject

"""
Job scheduling

A major issue in Paperwork are non-thread-safe dependencies (for instance,
libpoppler). This is solved by having only one thread other than the Gtk
main-loop thread. It is the job scheduler. Any long action is run in this
thread to avoid blocking the GUI.
"""

logger = logging.getLogger(__name__)


class JobException(Exception):

    def __init__(self, reason):
        Exception.__init__(self, reason)


class JobFactory(object):

    def __init__(self, name):
        self.name = name
        self.id_generator = itertools.count()

    def make(self, *args, **kwargs):
        """Child class must override this method"""
        raise NotImplementedError()

    def __eq__(self, other):
        return self is other


class Job(GObject.GObject):  # inherits from GObject so it can send signalsa

    MAX_TIME_FOR_UNSTOPPABLE_JOB = 0.5  # secs
    MAX_TIME_TO_STOP = 0.5  # secs

    # some jobs can be interrupted. In that case, the job should store in
    # the instance where it stopped, so it can resume its work when do()
    # is called again.
    # If can_stop = False, the job should never last more than
    # MAX_TIME_FOR_UNSTOPPABLE_JOB
    can_stop = False

    priority = 0  # the higher priority is run first

    started_by = None  # set by the scheduler

    already_started_once = False

    def __init__(self, job_factory, job_id):
        GObject.GObject.__init__(self)
        self.factory = job_factory
        self.id = job_id

        self._wait_time = None
        self._wait_cond = threading.Condition()

    def _wait(self, wait_time, force=False):
        """Convenience function to wait while being stoppable"""
        if self._wait_time is None or force:
            self._wait_time = wait_time

        start = time.time()
        self._wait_cond.acquire()
        try:
            self._wait_cond.wait(self._wait_time)
        finally:
            self._wait_cond.release()
            stop = time.time()
            self._wait_time -= (stop - start)

    def _stop_wait(self):
        self._wait_cond.acquire()
        try:
            self._wait_cond.notify_all()
        finally:
            self._wait_cond.release()

    def do(self):
        """Child class must override this method"""
        raise NotImplementedError()

    def stop(self, will_resume=False):
        """
        Only called if can_stop == True.
        Child class must override this method if can_stop == True.
        This function is run from the Gtk thread. It must *not* block
        """
        raise NotImplementedError()

    def __eq__(self, other):
        return self is other

    def __str__(self):
        return ("%s:%d" % (self.factory.name, self.id))


class JobScheduler(object):

    def __init__(self, name):
        self.name = name
        self._thread = None
        self.running = False

        # _job_queue_cond.acquire()/release() protect the job queue
        # _job_queue_cond.notify_all() is called each time the queue is
        # modified (except on cancel())
        self._job_queue_cond = threading.Condition()
        self._job_queue = []
        self._active_job = None

        self._job_idx_generator = itertools.count()

        self.warnings = True

    def start(self):
        """Starts the scheduler"""
        assert(not self.running)
        assert(self._thread is None)
        logger.info("[Scheduler %s] Starting" % self.name)
        self._thread = threading.Thread(target=self._run, name=self.name)
        self.running = True
        self._thread.start()

    def _run(self):
        logger.info("[Scheduler %s] Started" % self.name)

        while self.running:

            self._job_queue_cond.acquire()
            try:
                while len(self._job_queue) <= 0:
                    self._job_queue_cond.wait()
                    if not self.running:
                        return
                (_, _, self._active_job) = heapq.heappop(self._job_queue)
            finally:
                self._job_queue_cond.release()

            if not self.running:
                return

            # we are the only thread changing self._active_job,
            # so we can safely use it even if we didn't keep the lock
            # on self._job_queue_lock

            assert(self._active_job is not None)

            start = time.time()
            self._active_job.already_started_once = True
            try:
                self._active_job.do()
                logger.debug(
                    "[Scheduler %s] %s done", self.name, self._active_job
                )
            except Exception as exc:
                logger.error("===> Job %s raised an exception: %s: %s"
                             % (str(self._active_job),
                                type(exc), str(exc)))
                idx = 0
                for stack_el in traceback.extract_tb(sys.exc_info()[2]):
                    logger.error("%2d: %20s: L%5d: %s"
                                 % (idx, stack_el[0],
                                    stack_el[1], stack_el[2]))
                    idx += 1
                logger.error("---> Job %s was started by:"
                             % (str(self._active_job)))
                idx = 0
                for stack_el in self._active_job.started_by:
                    logger.error("%2d: %20s: L%5d: %s"
                                 % (idx, stack_el[0],
                                    stack_el[1], stack_el[2]))
                    idx += 1
            stop = time.time()

            diff = stop - start
            if (self._active_job.can_stop or
                    diff <= Job.MAX_TIME_FOR_UNSTOPPABLE_JOB):
                logger.debug("Job %s took %dms"
                             % (str(self._active_job), diff * 1000))
            elif self.warnings:
                logger.warning("Job %s took %dms and is unstoppable !"
                               " (maximum allowed: %dms)"
                               % (str(self._active_job), diff * 1000,
                                  Job.MAX_TIME_FOR_UNSTOPPABLE_JOB * 1000))

            self._job_queue_cond.acquire()
            try:
                logger.debug(
                    "[Scheduler %s] %d job(s) queued",
                    self.name, len(self._job_queue)
                )
                self._active_job = None
                self._job_queue_cond.notify_all()
            finally:
                self._job_queue_cond.release()

            if not self.running:
                return

    def _stop_active_job(self, will_resume=False):
        active_job = self._active_job

        if active_job.can_stop:
            logger.debug("[Scheduler %s] Job %s marked for stopping"
                         % (self.name, str(active_job)))
            active_job.stop(will_resume=will_resume)
        elif self.warnings:
            logger.warning(
                "[Scheduler %s] Tried to stop job %s, but it can't"
                " be stopped"
                % (self.name, str(active_job)))

    def schedule(self, job):
        """
        Schedule a job.

        Job are run by priority (higher first). If the given job
        has a priority higher than the one currently running, the scheduler
        will try to stop the running one, and start the given one instead.

        In case 2 jobs have the same priority, they are run in the order they
        were given.
        """
        logger.debug("[Scheduler %s] Queuing job %s"
                     % (self.name, str(job)))

        job.started_by = traceback.extract_stack()

        self._job_queue_cond.acquire()
        try:
            heapq.heappush(self._job_queue,
                           (-1 * job.priority, next(self._job_idx_generator),
                            job))

            # if a job with a lower priority is running, we try to stop
            # it and take its place
            active = self._active_job
            if (active is not None and
                    active.priority < job.priority):
                if not active.can_stop:
                    logger.debug("Job %s has a higher priority than %s,"
                                 " but %s can't be stopped"
                                 % (str(job), str(active), str(active)))
                else:
                    self._stop_active_job(will_resume=True)
                    # the active job may have already been re-queued
                    # previously. In which case we don't want to requeue
                    # it again
                    if active not in self._job_queue:
                        heapq.heappush(self._job_queue,
                                       (-1 * active.priority,
                                        next(self._job_idx_generator),
                                        active))

            self._job_queue_cond.notify_all()
            logger.debug(
                "[Scheduler %s] %d job(s) queued",
                self.name, len(self._job_queue)
            )
        finally:
            self._job_queue_cond.release()

    def _cancel_matching_jobs(self, condition):
        self._job_queue_cond.acquire()
        try:
            try:
                to_rm = []
                for job in self._job_queue:
                    if condition(job[2]):
                        to_rm.append(job)
                for job in to_rm:
                    self._job_queue.remove(job)
                    if job[2].already_started_once:
                        job[2].stop(will_resume=False)
                    logger.debug("[Scheduler %s] Job %s cancelled"
                                 % (self.name, str(job[2])))
            except ValueError:
                pass

            heapq.heapify(self._job_queue)
            if (self._active_job is not None and condition(self._active_job)):
                self._stop_active_job(will_resume=False)
        finally:
            self._job_queue_cond.release()

    def cancel(self, target_job):
        logger.debug("[Scheduler %s] Canceling job %s"
                     % (self.name, str(target_job)))
        self._cancel_matching_jobs(
            lambda job: (job == target_job))

    def cancel_all(self, factory):
        logger.debug("[Scheduler %s] Canceling all jobs %s"
                     % (self.name, factory.name))
        self._cancel_matching_jobs(
            lambda job: (job.factory == factory))

    def wait_for_all(self):
        had_to_wait = False
        while True:
            self._job_queue_cond.acquire()
            try:
                if not self._active_job and len(self._job_queue) <= 0:
                    return had_to_wait
                had_to_wait = True
                self._job_queue_cond.wait()
            finally:
                self._job_queue_cond.release()
        return had_to_wait

    def stop(self):
        assert(self.running)
        assert(self._thread is not None)
        logger.info("[Scheduler %s] Stopping" % self.name)

        self.running = False

        self._job_queue_cond.acquire()
        if self._active_job is not None:
            self._stop_active_job(will_resume=False)
        try:
            self._job_queue_cond.notify_all()
        finally:
            self._job_queue_cond.release()

        self._thread.join()
        self._thread = None

        logger.info("[Scheduler %s] Stopped" % self.name)


class JobProgressUpdater(Job):

    """
    Update a progress bar a predefined timing.
    """

    can_stop = True
    priority = 500
    NB_UPDATES = 50

    def __init__(self, factory, id, progressbar,
                 value_min=0.0, value_max=0.5, total_time=20.0):
        Job.__init__(self, factory, id)
        self.progressbar = progressbar
        self.value_min = float(value_min)
        self.value_max = float(value_max)
        self.total_time = float(total_time)

    def do(self):
        self.can_run = True

        for upd in range(0, self.NB_UPDATES):
            if not self.can_run:
                return

            val = self.value_max - self.value_min
            val *= upd
            val /= self.NB_UPDATES
            val += self.value_min

            GLib.idle_add(self.progressbar.set_fraction, val)
            self._wait(self.total_time / self.NB_UPDATES, force=True)

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobProgressUpdater)


class JobFactoryProgressUpdater(JobFactory):

    def __init__(self, progress_bar):
        JobFactory.__init__(self, "ProgressUpdater")
        self.progress_bar = progress_bar

    def make(self, value_min=0.0, value_max=0.5, total_time=20.0):
        job = JobProgressUpdater(self, next(self.id_generator),
                                 self.progress_bar, value_min, value_max,
                                 total_time)
        return job
