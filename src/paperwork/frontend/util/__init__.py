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

import locale
import logging
import os
import sys

import heapq
import gettext
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from pkg_resources import resource_filename

import PIL.Image

from .actions import SimpleAction

if os.name == "nt":
    import webbrowser
    from xml.etree import ElementTree

_ = gettext.gettext
logger = logging.getLogger(__name__)

PREFIX = os.environ.get('VIRTUAL_ENV', '/usr')


def translate_xml(xml_str):
    root = ElementTree.fromstring(xml_str)
    labels = root.findall('.//*[@name="label"][@translatable="yes"]')
    for label in labels:
        label.text = _(label.text)
    out = ElementTree.tostring(root, encoding='UTF-8')
    return out.decode('utf-8')


class ShowUriAction(SimpleAction):
    """
    WORKAROUND(JFlesch):
    On Windows without Python/Gobject installed by the user,
    Gtk.show_uri() doesn't seem to work.
    So we open the browser ourselves using Python lib.
    Worst case scenario, the browser is opened 2 times.
    """
    def __init__(self, uri):
        super().__init__("Open URI {}".format(uri))
        self.uri = uri

    def do(self, uri=None):
        super().do()
        uri = uri if uri else self.uri
        if uri is None:
            logger.warning("Should open a link, but don't know which one")
            return False
        webbrowser.open(uri)
        return False


def fix_widgets(widget_tree):
    for obj in widget_tree.get_objects():
        if isinstance(obj, Gtk.LinkButton):
            ShowUriAction(obj.get_uri()).connect([obj])
        elif isinstance(obj, Gtk.AboutDialog):
            action = ShowUriAction("(about dialog)")
            obj.connect(
                "activate-link", lambda widget, uri:
                GLib.idle_add(action.do, uri)
            )


def _get_resource_path(filename):
    """
    Gets the absolute location of a datafile located within the package
    (paperwork.frontend).
    This function throws if the file is not found, but the error depends on the
    way the package was installed.

    Arguments:
        filename -- the relative filename of the file to load.

    Returns:
        the full path of the file.

    Throws:
        Exception -- if the file is not found.

    """
    path = resource_filename('paperwork.frontend', filename)

    if not os.access(path, os.R_OK):
        raise FileNotFoundError(  # NOQA (Python 3.x only)
            "Can't find resource file '%s'. Aborting" % filename
        )

    logger.debug("For filename '%s' got file '%s'", filename, path)

    return path


def load_uifile(filename):
    """
    Load a .glade file and return the corresponding widget tree

    Arguments:
        filename -- glade filename to load.

    Returns:
        GTK Widget tree

    Throws:
        Exception -- If the file cannot be found
    """
    widget_tree = Gtk.Builder()

    ui_file = _get_resource_path(filename)

    if os.name == "nt":
        # WORKAROUND(Jflesch):
        # for some reason, add_from_file() doesn't translate
        # on Windows
        with open(ui_file, "r", encoding='utf-8') as file_desc:
            content = file_desc.read()
            xml_string = translate_xml(content)
            widget_tree.add_from_string(xml_string)
            fix_widgets(widget_tree)
    else:
        widget_tree.add_from_file(ui_file)

    return widget_tree


def load_cssfile(filename):
    """
    Load a .css file

    Arguments:
        filename -- css filename to load.

    Throws:
        Exception -- If the file cannot be found
    """
    css_provider = Gtk.CssProvider()

    css_file = _get_resource_path(filename)
    css_provider.load_from_path(css_file)

    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


_SIZEOF_FMT_STRINGS = [
    _('%3.1f bytes'),
    _('%3.1f KiB'),
    _('%3.1f MiB'),
    _('%3.1f GiB'),
    _('%3.1f TiB'),
]


def load_image(filename):
    """
    Load an image from Paperwork data
    """
    img = _get_resource_path(filename)
    return PIL.Image.open(img)


def preload_file(filename):
    """
    Just make sure Python make the file available to other elements (Gtk
    for instance)
    """
    try:
        _get_resource_path(filename)
    except FileNotFoundError:  # NOQA (Python 3.x only)
        logger.warning("Failed to preload '%s' !", filename)


def get_locale_dirs():
    locale_dirs = [
        "."
    ]

    # Pyinstaller support
    if getattr(sys, 'frozen', False):
        locale_dirs.append(os.path.join(sys._MEIPASS, "share"))

    # use the french locale file for reference
    try:
        path = resource_filename(
            'paperwork.frontend',
            os.path.join("share", "locale", "fr", "LC_MESSAGES")
        )
        for _ in range(0, 3):
            path = os.path.dirname(path)
        locale_dirs.append(path)
    except Exception as exc:
        logger.warning("Failed to locate locales !", exc_info=exc)

    return locale_dirs


def get_documentation(doc_name):
    """
    Return the path to a documentation PDF.
    Try to match the user language.
    """
    DOC_SUBDIR = "doc"

    lang = "en"
    try:
        lang = locale.getdefaultlocale()[0][:2]
    except:
        logger.exception(
            "get_documentation(): Failed to figure out locale. Will default"
            " to English"
        )
        pass

    default = os.path.join(DOC_SUBDIR, doc_name + ".pdf")
    localized = os.path.join(DOC_SUBDIR,
                             "{}_{}.pdf".format(doc_name, lang))
    try:
        return _get_resource_path(localized)
    except:
        pass

    try:
        return _get_resource_path(default)
    except:
        pass

    if os.path.exists(localized):
        return localized
    if os.path.exists(default):
        return default

    raise FileNotFoundError(  # NOQA (Python 3.x only)
        "Documentation {} not found !".format(doc_name)
    )


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

    def __next__(self):
        return self.next()

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
        else:
            raise ValueError()
        self.elements.remove(to_remove)
        heapq.heapify(self.elements)

    def __iter__(self):
        return PriorityQueueIter(self.elements)

    def __str__(self):
        return "PW[%s]" % (", ".join([str(x) for x in self.elements]))


def connect_actions(actions):
    for action in actions:
        for button in actions[action][0]:
            if button is None:
                logger.error("MISSING BUTTON: %s" % (action))
        try:
            actions[action][1].connect(actions[action][0])
        except:
            logger.error("Failed to connect action '%s'" % action)
            raise
