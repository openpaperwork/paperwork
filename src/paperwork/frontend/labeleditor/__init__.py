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

from paperwork.backend.labels import Label
from paperwork.frontend.util import load_uifile


_ = gettext.gettext
logger = logging.getLogger(__name__)


class LabelEditor(object):

    """
    Dialog to create / edit labels
    """

    def __init__(self, label_to_edit=None):
        if label_to_edit is None:
            label_to_edit = Label()
        self.label = label_to_edit

        self.__ok_button = None

    def edit(self, main_window):
        """
        Open the edit dialog, and update the label according to user changes
        """
        widget_tree = load_uifile(
            os.path.join("labeleditor", "labeleditor.glade"))

        dialog = widget_tree.get_object("dialogLabelEditor")
        name_entry = widget_tree.get_object("entryLabelName")
        color_chooser = widget_tree.get_object("colorselectionLabelColor")

        name_entry.set_text(self.label.name)
        name_entry.connect("changed", self.__on_label_entry_changed)
        color_chooser.set_current_color(self.label.color)

        dialog.set_transient_for(main_window)
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.__ok_button = dialog.add_button(_("Ok"), Gtk.ResponseType.OK)

        self.__on_label_entry_changed(name_entry)

        response = dialog.run()

        if (response == Gtk.ResponseType.OK
                and name_entry.get_text().strip() == ""):
            response = Gtk.ResponseType.CANCEL

        if (response == Gtk.ResponseType.OK):
            logger.info("Label validated")
            self.label.name = unicode(name_entry.get_text(), encoding='utf-8')
            self.label.color = color_chooser.get_current_color()
        else:
            logger.info("Label editing cancelled")

        dialog.destroy()

        logger.info("Label after editing: %s" % self.label)
        return (response == Gtk.ResponseType.OK)

    def __on_label_entry_changed(self, label_entry):
        txt = unicode(label_entry.get_text(), encoding='utf-8').strip()
        ok_enabled = True
        ok_enabled = ok_enabled and txt != u""
        ok_enabled = ok_enabled and u"," not in txt
        self.__ok_button.set_sensitive(ok_enabled)
