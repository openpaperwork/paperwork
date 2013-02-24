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

import Image
import gettext

from gi.repository import GObject

from paperwork.frontend.img_cutting import ImgGripHandler
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


class PageEditingDialog(object):
    def __init__(self, main_window, page):
        self.page = page

        widget_tree = load_uifile("pageeditingdialog.glade")

        self.__dialog = widget_tree.get_object("dialogPageEditing")
        self.__dialog.set_transient_for(main_window.window)

        self.__original_img_widgets = {
            'img' : widget_tree.get_object("imageOriginal"),
            'eventbox' : widget_tree.get_object("eventboxOriginal"),
            'viewport' : widget_tree.get_object("viewportOriginal")
        }
        self.cutting_button = widget_tree.get_object("togglebuttonCutting")

        self.__cut_grips = None

        self.__original_img_widgets['viewport'].connect("size-allocate",
            lambda widget, size: GObject.idle_add(self.__on_size_allocated_cb))
        self.cutting_button.connect("toggled",
            lambda widget: GObject.idle_add(self.__on_cutting_button_toggled_cb))


        self.page = page
        self.imgs = {
            'orig' : (1.0, self.page.img)
        }


    def __on_size_allocated_cb(self):
        if not self.__cut_grips is None:
            return
        (a, b, img_w, img_h) = self.imgs['orig'][1].getbbox()
        orig_alloc = self.__original_img_widgets['viewport'].get_allocation()
        (orig_alloc_w, orig_alloc_h) = (orig_alloc.width, orig_alloc.height)
        factor_w = (float(orig_alloc_w) / img_w)
        factor_h = (float(orig_alloc_h) / img_h)
        factor = min(factor_w, factor_h)
        if factor > 1.0:
            factor = 1.0
        target_size = (int(factor * img_w), int(factor * img_h))
        self.imgs['resized'] = (factor, self.imgs['orig'][1].resize(
                    target_size, Image.BILINEAR))
        self.__cut_grips = ImgGripHandler(
            [self.imgs['resized'], self.imgs['orig']],
            self.__original_img_widgets['eventbox'],
            self.__original_img_widgets['img'])
        self.__cut_grips.visible = False

    def __on_cutting_button_toggled_cb(self):
        self.__cut_grips.visible = self.cutting_button.get_active()

    def get_changes(self):
        resp_id = self.__dialog.run()
        self.__dialog.destroy()
        if resp_id == 1:  # cancel
            print "Image editing cancelled by user"
            return []
        # TODO
        return []
