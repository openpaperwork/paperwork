#!/usr/bin/env python
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

import logging
import os

import heapq
import gettext
from gi.repository import Gtk


_ = gettext.gettext
logger = logging.getLogger(__name__)

PREFIX = os.environ.get('VIRTUAL_ENV', '/usr')

UI_FILES_DIRS = [
    ".",
    "src/paperwork/frontend",
    PREFIX + "/share/paperwork",
    PREFIX + "/local/share/paperwork",
]


def load_uifile(filename):
    """
    Load a .glade file and return the corresponding widget tree

    Arguments:
        filename -- glade filename to load. Must not contain any directory
            name, just the filename. This function will (try to) figure out
            where it must be found.

    Returns:
        GTK Widget tree

    Throws:
        Exception -- If the file cannot be found
    """
    widget_tree = Gtk.Builder()
    has_ui_file = False
    for ui_dir in UI_FILES_DIRS:
        ui_file = os.path.join(ui_dir, filename)
        if os.access(ui_file, os.R_OK):
            logging.info("UI file used: " + ui_file)
            widget_tree.add_from_file(ui_file)
            has_ui_file = True
            break
    if not has_ui_file:
        logging.error("Can't find resource file '%s'. Aborting" % filename)
        raise Exception("Can't find resource file '%s'. Aborting" % filename)
    return widget_tree


_SIZEOF_FMT_STRINGS = [
    _('%3.1f bytes'),
    _('%3.1f KB'),
    _('%3.1f MB'),
    _('%3.1f GB'),
    _('%3.1f TB'),
]


def sizeof_fmt(num):
    """
    Format a number of bytes in a human readable way
    """
    for string in _SIZEOF_FMT_STRINGS:
        if num < 1024.0:
            return string % (num)
        num /= 1024.0
    return _SIZEOF_FMT_STRINGS[-1] % (num)


class PriorityQueueIter(object):

    def __init__(self, queue):
        """
        Arguments:
            queue --- must actually be an heapq
        """
        self.queue = queue[:]

    def next(self):
        try:
            return heapq.heappop(self.queue)[2]
        except IndexError:
            raise StopIteration()

    def __iter__(self):
        return self


class PriorityQueue(object):

    def __init__(self):
        self.__last_idx = 0
        self.elements = []

    def purge(self):
        self.elements = []

    def add(self, priority, element):
        """
        Elements with a higher priority are returned first
        """
        heapq.heappush(
            self.elements,
            (-1 * priority, self.__last_idx, element)
        )
        self.__last_idx += 1

    def remove(self, target):
        to_remove = None
        for element in self.elements:
            if element[2] == target:
                to_remove = element
                break
        if to_remove is None:
            raise ValueError()
        self.elements.remove(to_remove)
        heapq.heapify(self.elements)

    def __iter__(self):
        return PriorityQueueIter(self.elements)

    def __str__(self):
        return "PW[%s]" % (", ".join([str(x) for x in self.elements]))
