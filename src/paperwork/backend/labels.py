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
        if type(name) == unicode:
            self.name = name
        else:
            self.name = unicode(name, encoding='utf-8')
        self.color = Gdk.color_parse(color)

    def __copy__(self):
        return Label(self.name, self.get_color_str())

    def __label_cmp(self, other):
        """
        Comparaison function. Can be used to sort labels alphabetically.
        """
        if other is None:
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

    def __hash__(self):
        return hash(self.name)

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
                % (self.get_html_color(), self.name))
