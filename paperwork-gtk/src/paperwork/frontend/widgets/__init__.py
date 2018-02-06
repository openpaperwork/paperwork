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

import os

import gettext
import logging

from gi.repository import Gtk

_ = gettext.gettext
logger = logging.getLogger(__name__)


class LabelColorButton(Gtk.ColorButton):

    __gtype_name__ = 'LabelColorButton'

    """
    Color button which opens no GtkColorChooserDialog on click
    """

    def __new__(cls, *args, **kwargs):
        return Gtk.ColorButton.__new__(cls, *args, **kwargs)

    def __init__(cls):
        super(LabelColorButton, cls).__init__()

    def do_clicked(self):
        """
        Do not open a GtkColorChooserDialog
        """
        pass

