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

"""
Code to manage document labels
"""

from gi.repository import Gdk
from gi.repository import Gtk

from paperwork.util import load_uifile


class Label(object):
    """
    Represents a Label (color + string).
    """

    def __init__(self, name=u"", color="#000000000000"):
        """
        Arguments:
            name --- label name
            color --- label color (string representation, see get_color_str())
        """
        self.name = unicode(name)
        self.color = Gdk.color_parse(color)

    def __copy__(self):
        return Label(self.name, self.get_color_str())

    def __label_cmp(self, other):
        """
        Comparaison function. Can be used to sort labels alphabetically.
        """
        if other == None:
            return -1
        cmp_r = cmp(self.name, other.name)
        if cmp_r != 0:
            return cmp_r
        return cmp(self.get_color_str(), other.get_color_str())

    def __lt__(self, other):
        return self.__label_cmp(other) < 0

    def __gt__(self, other):
        return self.__label_cmp(other) > 0

    def __eq__(self, other):
        return self.__label_cmp(other) == 0

    def __le__(self, other):
        return self.__label_cmp(other) <= 0

    def __ge__(self, other):
        return self.__label_cmp(other) >= 0

    def __ne__(self, other):
        return self.__label_cmp(other) != 0

    def get_html_color(self):
        """
        get a string representing the color, using HTML notation
        """
        return ("#%02X%02X%02X" % (self.color.red >> 8, self.color.green >> 8,
                                   self.color.blue >> 8))

    def get_color_str(self):
        """
        Returns a string representation of the color associated to this label.
        """
        return self.color.to_string()

    def get_html(self):
        """
        Returns a HTML string that represent the label. Can be used with GTK.
        """
        return ("<span bgcolor=\"%s\">    </span> %s"
                % (self.get_html_color(), self.name))

    def __str__(self):
        return ("Color: %s ; Text: %s"
                % (self.get_html_color(),
                   self.name.encode('ascii', 'replace')))


class LabelEditor(object):
    """
    Dialog to create / edit labels
    """

    def __init__(self, label_to_edit=None):
        if label_to_edit == None:
            label_to_edit = Label()
        self.label = label_to_edit

    def edit(self, main_window):
        """
        Open the edit dialog, and update the label according to user changes
        """
        widget_tree = load_uifile("labeledit.glade")

        dialog = widget_tree.get_object("dialogLabelEditor")
        name_entry = widget_tree.get_object("entryLabelName")
        color_chooser = widget_tree.get_object("colorselectionLabelColor")

        name_entry.set_text(self.label.name)
        color_chooser.set_current_color(self.label.color)

        dialog.set_transient_for(main_window)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Ok", Gtk.ResponseType.OK)
        response = dialog.run()

        if (response == Gtk.ResponseType.OK
            and name_entry.get_text().strip() == ""):
            response = Gtk.ResponseType.CANCEL
        if (response == Gtk.ResponseType.OK):
            print "Label validated"
            self.label.name = unicode(name_entry.get_text())
            self.label.color = color_chooser.get_current_color()
        else:
            print "Label editing cancelled"

        dialog.destroy()

        print "Label after editing: %s" % (self.label)
        return (response == Gtk.ResponseType.OK)
