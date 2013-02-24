#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2013  Jerome Flesch
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

import gettext

from gi.repository import GObject

from paperwork.util import image2pixbuf
from paperwork.util import load_uifile


_ = gettext.gettext


class PageEditionAction(object):
    def __init__(self):
        pass

    def do(self, img):
        raise NotImplementedError()

    def add_to_action_queue(self, actions):
        raise NotImplementedError()

    def __str__(self):
        raise NotImplementedError()


class PageRotationAction(PageEditionAction):
    def __init__(self, angle):
        PageEditionAction.__init__(self)
        self.angle = angle

    def do(self, img):
        # TODO
        pass

    def add_to_action_queue(self, actions):
        # TODO
        pass

    def __str__(self):
        return _("Image rotation of %d degrees") % self.angle


class PageCuttingAction(PageEditionAction):
    def __init__(self, cut):
        """
        Arguments:
            cut --- ((a, b), (c, d)) : a, b, c, d are float between 0.0 and 1.0
            (1.0 being the whole image weight/height)
        """
        self.cut = cut

    def do(self, img):
        # TODO
        pass

    def add_to_action_queue(self, action):
        # TODO
        pass

    def __str__(self):
        return _("Image cutting: %s") % str(self.cut)


class PageEditingDialog(GObject.GObject):
    __gsignals__ = {
        'page-changes' : (GObject.SignalFlags.RUN_LAST, None,
                          (GObject.TYPE_PYOBJECT,  # array of PageEditionAction
                          ))
    }

    def __init__(self, main_window, page):
        widget_tree = load_uifile("pageeditingdialog.glade")

        self.__dialog = widget_tree.get_object("dialogPageEditing")
        self.__dialog.set_transient_for(main_window.window)

        self.page = page

    def run(self):
        resp_id = self.__dialog.run()
        self.__dialog.destroy()
        if resp_id == 1:  # cancel
            print "Image editing cancelled by user"
            return


GObject.type_register(PageEditingDialog)

