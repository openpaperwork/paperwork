import logging
import time


class UnixTimeStampLogFormatter(logging.Formatter):
    program_start = time.time()

    def formatTime(self, record, datefmt=None):
        return "{0:.6f}".format(record.created - self.program_start)
