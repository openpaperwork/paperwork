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

import PIL.Image
import gettext
import logging

from gi.repository import GObject

from paperwork.frontend.img_cutting import ImgGripHandler
from paperwork.util import image2pixbuf
from paperwork.util import load_uifile

_ = gettext.gettext
logger = logging.getLogger(__name__)


class PageEditionAction(object):
    def __init__(self):
        pass

    def do(self, img, img_scale):
        raise NotImplementedError()

    def add_to_action_queue(self, actions):
        raise NotImplementedError()

    def __str__(self):
        raise NotImplementedError()


class PageRotationAction(PageEditionAction):
    def __init__(self, angle):
        PageEditionAction.__init__(self)
        self.angle = angle

    def do(self, img, img_scale):
        # PIL angle is counter-clockwise. Ours is clockwise
        return img.rotate(angle=-1 * self.angle)

    def add_to_action_queue(self, actions):
        for action in actions:
            if isinstance(action, PageRotationAction):
                self.angle += action.angle
                actions.remove(action)
        actions.append(self)

    def __str__(self):
        return _("Image rotation of %d degrees") % self.angle


class PageCuttingAction(PageEditionAction):
    def __init__(self, cut):
        """
        Arguments:
            cut --- ((a, b), (c, d))
        """
        self.cut = cut

    def do(self, img, img_scale):
        cut = (int(float(self.cut[0][0]) * img_scale),
               int(float(self.cut[0][1]) * img_scale),
               int(float(self.cut[1][0]) * img_scale),
               int(float(self.cut[1][1]) * img_scale))
        return img.crop(cut)

    def add_to_action_queue(self, actions):
        self.remove_from_action_queue(actions)
        actions.insert(0, self)

    @staticmethod
    def remove_from_action_queue(actions):
        for action in actions:
            if isinstance(action, PageCuttingAction):
                actions.remove(action)

    def __str__(self):
        return _("Image cutting: %s") % str(self.cut)


class PageEditingDialog(object):
    def __init__(self, main_window, page):
        self.page = page

        widget_tree = load_uifile("pageeditingdialog.glade")

        self.__dialog = widget_tree.get_object("dialogPageEditing")
        self.__dialog.set_transient_for(main_window.window)

        self.__original_img_widgets = {
            'img': widget_tree.get_object("imageOriginal"),
            'scrolledwindow': widget_tree.get_object("scrolledwindowOriginal"),
            'eventbox': widget_tree.get_object("eventboxOriginal"),
            'viewport': widget_tree.get_object("viewportOriginal")
        }
        self.__result_img_widget = widget_tree.get_object("imageResult")
        self.__buttons = {
            'cutting': widget_tree.get_object("togglebuttonCutting"),
            'rotate': {
                'clockwise': (widget_tree.get_object("buttonRotateClockwise"),
                              90),
                'counter_clockwise':
                (widget_tree.get_object("buttonRotateCounterClockwise"), -90),
            }
        }

        self.__cut_grips = None

        self.__original_img_widgets['viewport'].connect(
            "size-allocate",
            lambda widget, size: GObject.idle_add(self.__on_size_allocated_cb))
        self.__buttons['cutting'].connect(
            "toggled",
            lambda widget: GObject.idle_add(
                self.__on_cutting_button_toggled_cb))
        self.__buttons['rotate']['clockwise'][0].connect(
            "clicked",
            lambda widget:
            GObject.idle_add(self.__on_rotate_activated_cb, widget))
        self.__buttons['rotate']['counter_clockwise'][0].connect(
            "clicked",
            lambda widget:
            GObject.idle_add(self.__on_rotate_activated_cb, widget))

        self.page = page
        self.imgs = {
            'orig': (1.0, self.page.img)
        }

        self.__changes = []

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
        copy = self.imgs['orig'][1].copy()
        self.imgs['resized'] = (factor,
                                copy.resize(target_size, PIL.Image.BILINEAR))
        self.__cut_grips = ImgGripHandler(
            [self.imgs['resized'], self.imgs['orig']],
            self.__original_img_widgets['scrolledwindow'],
            self.__original_img_widgets['eventbox'],
            self.__original_img_widgets['img'])
        self.__cut_grips.visible = False
        self.__cut_grips.connect("grip-moved", self.__on_grip_moved_cb)

        self.__redraw_result()

    def __on_cutting_button_toggled_cb(self):
        self.__cut_grips.visible = self.__buttons['cutting'].get_active()
        if not self.__cut_grips.visible:
            PageCuttingAction.remove_from_action_queue(self.__changes)
            self.__redraw_result()
        else:
            self.__on_grip_moved_cb(self.__cut_grips)

    def __on_grip_moved_cb(self, grips):
        cut = self.__cut_grips.get_coords()
        action = PageCuttingAction(cut)
        action.add_to_action_queue(self.__changes)
        self.__redraw_result()

    def __on_rotate_activated_cb(self, widget):
        for (button, angle) in self.__buttons['rotate'].values():
            if button == widget:
                break
        assert(button is not None)
        logger.info("Adding action rotation of %d degrees" % angle)
        rotation = PageRotationAction(angle)
        rotation.add_to_action_queue(self.__changes)
        self.__redraw_result()

    def __redraw_result(self):
        (scale, img) = self.imgs['resized']
        for action in self.__changes:
            img = action.do(img, scale)
        img = image2pixbuf(img)
        self.__result_img_widget.set_from_pixbuf(img)

    def get_changes(self):
        resp_id = self.__dialog.run()
        self.__dialog.destroy()
        if resp_id == 1:  # cancel
            logger.info("Image editing cancelled by user")
            return []
        return self.__changes
