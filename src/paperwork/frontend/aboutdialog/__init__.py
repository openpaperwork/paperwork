#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
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
Contains the code relative to the about dialog (the one you get when you click
on Help->About)
"""

import os
import sys

from gi.repository import GdkPixbuf

from paperwork.frontend.util import load_uifile


class AboutDialog(object):

    """
    Dialog that appears when you click Help->About.

    By default, this dialog won't be visible. You have to call
    AboutDialog.show().
    """

    def __init__(self, main_window):
        self.__widget_tree = load_uifile(
            os.path.join("aboutdialog", "aboutdialog.glade"))

        self.__dialog = self.__widget_tree.get_object("aboutdialog")
        assert(self.__dialog)
        self.__dialog.set_transient_for(main_window)

        logo_path = os.path.join(
            sys.prefix, 'share', 'icons', 'hicolor', 'scalable', 'apps',
            'paperwork.svg'
        )
        if os.access(logo_path, os.F_OK):
            logo = GdkPixbuf.Pixbuf.new_from_file(logo_path)
            self.__dialog.set_logo(logo)
        self.__dialog.connect("response", lambda x, y: x.destroy())

    def show(self):
        """
        Make the about dialog appears
        """
        self.__dialog.set_visible(True)
