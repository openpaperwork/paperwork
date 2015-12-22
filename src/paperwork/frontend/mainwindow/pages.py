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
import math
import threading

import gettext

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import PangoCairo
import PIL.Image

from paperwork.backend.common.page import BasicPage
from paperwork.backend.util import image2surface
from paperwork.backend.util import split_words
from paperwork.frontend.util.canvas.animations import SpinnerAnimation
from paperwork.frontend.util.canvas.drawers import Drawer
from paperwork.frontend.util.imgcutting import ImgGripHandler
from paperwork.frontend.util.jobs import Job
from paperwork.frontend.util.jobs import JobFactory


_ = gettext.gettext
logger = logging.getLogger(__name__)


class JobPageImgLoader(Job):
    can_stop = True
    priority = 500

    __gsignals__ = {
        'page-loading-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'page-loading-img': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_PYOBJECT,)),
        'page-loading-done': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, factory, job_id, page, size):
        Job.__init__(self, factory, job_id)
        self.page = page
        self.size = size
        self.__cond = threading.Condition()

    def do(self):
        self.__cond.acquire()
        try:
            self.can_run = True
            self.emit('page-loading-start')
            self.__cond.wait(0.1)
        finally:
            self.__cond.release()

        try:
            if not self.can_run:
                return

            use_thumbnail = True
            if self.size[1] > (BasicPage.DEFAULT_THUMB_HEIGHT * 1.5):
                use_thumbnail = False
            if not self.can_run:
                return
            if not use_thumbnail:
                img = self.page.img
            else:
                img = self.page.get_thumbnail(BasicPage.DEFAULT_THUMB_WIDTH,
                                              BasicPage.DEFAULT_THUMB_HEIGHT)
            if not self.can_run:
                return
            if self.size != img.size:
                img = img.resize(self.size, PIL.Image.ANTIALIAS)
            if not self.can_run:
                return
            img.load()
            if not self.can_run:
                return
            self.emit('page-loading-img', image2surface(img))

        finally:
            self.emit('page-loading-done')

    def stop(self, will_resume=False):
        self.__cond.acquire()
        try:
            self.can_run = False
            self.__cond.notify_all()
        finally:
            self.__cond.release()


GObject.type_register(JobPageImgLoader)


class JobFactoryPageImgLoader(JobFactory):

    def __init__(self):
        JobFactory.__init__(self, "PageImgLoader")

    def make(self, drawer, page, size):
        job = JobPageImgLoader(self, next(self.id_generator), page, size)
        job.connect('page-loading-img',
                    lambda job, img:
                    GLib.idle_add(drawer.on_page_loading_img,
                                  job.page, img))
        job.connect('page-loading-done',
                    lambda job:
                    GLib.idle_add(drawer.on_page_loading_done,
                                  job.page))
        return job


class JobPageBoxesLoader(Job):
    can_stop = True
    priority = 100

    __gsignals__ = {
        'page-loading-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'page-loading-boxes': (GObject.SignalFlags.RUN_LAST, None,
                               (
                                   GObject.TYPE_PYOBJECT,  # all boxes
                               )),
        'page-loading-done': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, factory, job_id, page):
        Job.__init__(self, factory, job_id)
        self.page = page
        self.__cond = threading.Condition()

    def do(self):
        self.can_run = True
        self.emit('page-loading-start')
        try:
            line_boxes = self.page.boxes

            self.__cond.acquire()
            try:
                self.__cond.wait(0.5)
            finally:
                self.__cond.release()
            if not self.can_run:
                self.emit('page-loading-done')

            boxes = []
            for line in line_boxes:
                boxes += line.word_boxes

            self.emit('page-loading-boxes', boxes)
        finally:
            self.emit('page-loading-done')

    def stop(self, will_resume=False):
        self.can_run = False
        self.__cond.acquire()
        try:
            self.__cond.notify_all()
        finally:
            self.__cond.release()


GObject.type_register(JobPageBoxesLoader)


class JobFactoryPageBoxesLoader(JobFactory):

    def __init__(self):
        JobFactory.__init__(self, "PageBoxesLoader")

    def make(self, drawer, page):
        job = JobPageBoxesLoader(self, next(self.id_generator), page)
        job.connect('page-loading-boxes',
                    lambda job, all_boxes:
                    GLib.idle_add(drawer.on_page_loading_boxes,
                                  job.page, all_boxes))
        return job


class PageEditionAction(object):
    def __init__(self):
        pass

    def do(self, img):
        raise NotImplementedError()

    def __str__(self):
        raise NotImplementedError()


class PageRotationAction(PageEditionAction):

    def __init__(self, angle):
        PageEditionAction.__init__(self)
        self.angle = angle

    def do(self, img):
        # PIL angle is counter-clockwise. Ours is clockwise
        return img.rotate(angle=-1 * self.angle, expand=True)

    def __str__(self):
        return _("Image rotation of %d degrees") % self.angle


class PageCuttingAction(PageEditionAction):
    def __init__(self, cut):
        """
        Arguments:
            cut --- ((a, b), (c, d))
        """
        self.cut = cut

    def do(self, img):
        cut = (int(self.cut[0][0]),
               int(self.cut[0][1]),
               int(self.cut[1][0]),
               int(self.cut[1][1]))
        return img.crop(cut)

    def __str__(self):
        return _("Image cutting: %s") % str(self.cut)


class PageDrawer(Drawer, GObject.GObject):
    layer = Drawer.IMG_LAYER
    LINE_WIDTH = 1.0
    MARGIN = 20
    BORDER_BASIC = (5, (0.85, 0.85, 0.85))
    BORDER_HIGHLIGHTED = (5, (0, 0.85, 0))
    TMP_AREA = (0.85, 0.85, 0.85)

    BUTTON_SIZE = 32
    BUTTON_BACKGROUND = (0.85, 0.85, 0.85)
    TOOLTIP_LENGTH = 200
    FONT_SIZE = 15
    ICON_EDIT_START = "document-properties"
    ICON_EDIT_CROP = "edit-cut"
    ICON_EDIT_ROTATE_COUNTERCLOCKWISE = "object-rotate-left"
    ICON_EDIT_ROTATE_CLOCKWISE = "object-rotate-right"
    ICON_EDIT_CANCEL = "edit-undo"
    ICON_EDIT_APPLY = "document-save"
    ICON_DELETE = "edit-delete"

    PAGE_DRAG_ID = 128

    __gsignals__ = {
        'page-selected': (GObject.SignalFlags.RUN_LAST, None, ()),
        'page-edited': (GObject.SignalFlags.RUN_LAST, None,
                        (
                            GObject.TYPE_PYOBJECT,  # List of PageEditionAction
                        )),
        'page-deleted': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, page,
                 job_factories,
                 job_schedulers,
                 previous_page_drawer=None,
                 show_boxes=True,
                 show_all_boxes=False,
                 show_border=False,
                 enable_editor=False,
                 sentence=u""):
        GObject.GObject.__init__(self)
        Drawer.__init__(self)

        self.max_size = page.size
        self.page = page
        self.show_boxes = show_boxes
        self.show_all_boxes = show_all_boxes
        self.show_border = show_border
        self.enable_editor = enable_editor
        self.mouse_over = False
        self.mouse_over_button = None
        self.previous_page_drawer = previous_page_drawer
        self.is_drag_source = False
        self.drag_enabled = True

        self.surface = None
        self.boxes = {
            'all': set(),
            'highlighted': set(),
            'mouse_over': None,
        }
        self.sentence = sentence
        self.visible = False
        self.loading = False

        self.factories = job_factories
        self.schedulers = job_schedulers

        self._size = self.max_size
        self._position = (0, 0)
        self.angle = 0
        self.spinner = SpinnerAnimation((0, 0))
        self.upd_spinner_position()

        icon_theme = Gtk.IconTheme.get_default()

        first_editor_buttons = []
        first_editor_buttons_pos = 10

        if self.page.can_edit:
            first_editor_buttons.append(
                # button 'start edit'
                ((-10 - self.BUTTON_SIZE, first_editor_buttons_pos),
                 icon_theme.lookup_icon(
                     self.ICON_EDIT_START, self.BUTTON_SIZE,
                     Gtk.IconLookupFlags.NO_SVG).load_icon(),
                 self._on_edit_start,
                 _("Edit")),
            )
            first_editor_buttons_pos += 10 + self.BUTTON_SIZE

        if self.page.doc.can_edit:
            first_editor_buttons.append(
                # button 'delete'
                ((-10 - self.BUTTON_SIZE, first_editor_buttons_pos),
                 icon_theme.lookup_icon(
                     self.ICON_DELETE, self.BUTTON_SIZE,
                     Gtk.IconLookupFlags.NO_SVG).load_icon(),
                 self._on_delete,
                 _("Delete page")),
            )
            first_editor_buttons_pos += 10 + self.BUTTON_SIZE

        self.editor_buttons = {
            "before": first_editor_buttons,
            "during": [
                # button 'cancel'
                ((-10 - self.BUTTON_SIZE, 10 + (0 * (10 + self.BUTTON_SIZE))),
                 icon_theme.lookup_icon(
                     self.ICON_EDIT_CANCEL, self.BUTTON_SIZE,
                     Gtk.IconLookupFlags.NO_SVG).load_icon(),
                 self._on_edit_cancel,
                 _("Cancel")),
                # button 'crop'
                ((-10 - self.BUTTON_SIZE, 10 + (1 * (10 + self.BUTTON_SIZE))),
                 icon_theme.lookup_icon(
                     self.ICON_EDIT_CROP, self.BUTTON_SIZE,
                     Gtk.IconLookupFlags.NO_SVG).load_icon(),
                 self._on_edit_crop,
                 _("Crop")),
                # button 'rotate_counter_clockwise'
                ((-10 - self.BUTTON_SIZE, 10 + (2 * (10 + self.BUTTON_SIZE))),
                 icon_theme.lookup_icon(
                     self.ICON_EDIT_ROTATE_COUNTERCLOCKWISE, self.BUTTON_SIZE,
                     Gtk.IconLookupFlags.NO_SVG).load_icon(),
                 self._on_edit_counterclockwise,
                 _("Rotate counter-clockwise")),
                # button 'rotate_clockwise'
                ((-10 - self.BUTTON_SIZE, 10 + (3 * (10 + self.BUTTON_SIZE))),
                 icon_theme.lookup_icon(
                     self.ICON_EDIT_ROTATE_CLOCKWISE, self.BUTTON_SIZE,
                     Gtk.IconLookupFlags.NO_SVG).load_icon(),
                 self._on_edit_clockwise,
                 _("Rotate clockwise")),
                # button 'done'
                ((-10 - self.BUTTON_SIZE, 10 + (4 * (10 + self.BUTTON_SIZE))),
                 icon_theme.lookup_icon(
                     self.ICON_EDIT_APPLY, self.BUTTON_SIZE,
                     Gtk.IconLookupFlags.NO_SVG).load_icon(),
                 self._on_edit_apply,
                 _("Apply")),
            ]
        }
        self.editor_state = "before"
        self.editor_grips = None

    def relocate(self):
        assert(self.canvas)
        if self.previous_page_drawer is None:
            position_h = self.MARGIN
            position_w = self.MARGIN
        elif (self.previous_page_drawer.position[0]
              + self.previous_page_drawer.size[0]
              + (2 * self.MARGIN)
              + self.size[0]
              < self.canvas.visible_size[0]):
            position_w = (self.previous_page_drawer.position[0]
                          + self.previous_page_drawer.size[0]
                          + (2 * self.MARGIN))
            position_h = self.previous_page_drawer.position[1]
        else:
            position_w = self.MARGIN
            position_h = (self.previous_page_drawer.position[1]
                          + self.previous_page_drawer.size[1]
                          + (2 * self.MARGIN))
        self.position = (position_w, position_h)

    def set_canvas(self, canvas):
        Drawer.set_canvas(self, canvas)
        self.spinner.set_canvas(canvas)
        self.relocate()
        canvas.connect(self, "absolute-motion-notify-event",
                       lambda canvas, event:
                       GLib.idle_add(self._on_mouse_motion, event))
        canvas.connect(self, "absolute-button-release-event",
                       lambda canvas, event:
                       GLib.idle_add(self._on_mouse_button_release, event))
        canvas.connect(self, "size-allocate", self._on_size_allocate_cb)

        canvas.connect(self, "drag-begin", self._on_drag_begin)
        canvas.connect(self, "drag-data-get", self._on_drag_data_get)
        canvas.connect(self, "drag-end", self._on_drag_end)
        canvas.connect(self, "drag-failed", self._on_drag_failed)

    def _on_drag_begin(self, canvas, drag_context):
        if not self.mouse_over:
            return
        page_id = self.page.id
        logger.info("Drag-n-drop begin: selected: [%s]" % page_id)
        self.is_drag_source = True
        self.redraw()

    def _on_drag_data_get(self, canvas, drag_context, data, info, time):
        if not self.is_drag_source:
            return
        page_id = self.page.id
        logger.info("Drag-n-drop get: selected: [%s]" % page_id)
        data.set_text(unicode(page_id), -1)

    def _on_drag_failed(self, canvas, drag_context, result):
        if not self.is_drag_source:
            return
        page_id = self.page.id
        logger.info("Drag-n-drop failed: %d ([%s])" % (result, page_id))
        self.is_drag_source = False

    def _on_drag_end(self, canvas, drag_context):
        if not self.is_drag_source:
            return
        page_id = self.page.id
        logger.info("Drag-n-drop end: selected: [%s]" % page_id)
        self.is_drag_source = False
        self.redraw()

    def _on_size_allocate_cb(self, widget, size):
        GLib.idle_add(self.relocate)

    def on_tick(self):
        Drawer.on_tick(self)
        self.spinner.on_tick()

    def upd_spinner_position(self):
        self.spinner.position = (
            (self._position[0] + (self._size[0] / 2)
             - (SpinnerAnimation.ICON_SIZE / 2)),
            (self._position[1] + (self._size[1] / 2)
             - (SpinnerAnimation.ICON_SIZE / 2)),
        )

    def _get_position(self):
        return self._position

    def _set_position(self, position):
        self._position = position
        self.upd_spinner_position()

    position = property(_get_position, _set_position)

    def _get_size(self):
        return self._size

    def _set_size(self, size):
        if size == self._size:
            return

        if self.editor_grips:
            # TODO(Jflesch): resize grips
            pass

        self._size = size
        self.unload_content()
        self.visible = False  # will force a reload if visible
        self.upd_spinner_position()

    size = property(_get_size, _set_size)

    def set_size_ratio(self, factor):
        self.size = (int(factor * self.max_size[0]),
                     int(factor * self.max_size[1]))

    def load_content(self):
        if self.loading:
            return
        self.canvas.add_drawer(self.spinner)
        self.loading = True
        job = self.factories['page_img_loader'].make(self, self.page,
                                                     self.size)
        self.schedulers['page_img_loader'].schedule(job)

    def on_page_loading_img(self, page, surface):
        if not self.visible:
            return
        self.surface = surface
        if (len(self.boxes['all']) <= 0
                and (self.show_boxes or self.show_border)):
            job = self.factories['page_boxes_loader'].make(self, self.page)
            self.schedulers['page_boxes_loader'].schedule(job)

    def on_page_loading_done(self, page):
        if self.loading:
            self.canvas.remove_drawer(self.spinner)
            self.loading = False
        if self.visible and not self.surface:
            self.load_content()

    def _get_highlighted_boxes(self, sentence):
        """
        Get all the boxes corresponding the given sentence

        Arguments:
            sentence --- can be string (will be splited), or an array of
                strings
        Returns:
            an array of boxes (see pyocr boxes)
        """
        if isinstance(sentence, unicode):
            keywords = split_words(sentence)
        else:
            assert(isinstance(sentence, list))
            keywords = sentence

        output = set()
        for keyword in keywords:
            for box in self.boxes["all"]:
                if keyword in box.content:
                    output.add(box)
                    continue
                # unfold generator output
                words = [x for x in split_words(box.content)]
                if keyword in words:
                    output.add(box)
                    continue
        return output

    def reload_boxes(self, new_sentence=None):
        if new_sentence:
            self.sentence = new_sentence
        self.boxes["highlighted"] = self._get_highlighted_boxes(self.sentence)
        self.redraw()

    def on_page_loading_boxes(self, page, all_boxes):
        if not self.visible:
            return
        self.boxes['all'] = set(all_boxes)
        self.reload_boxes()

    def unload_content(self):
        if self.loading:
            self.canvas.remove_drawer(self.spinner)
            self.loading = False
        if self.surface is not None:
            del(self.surface)
            self.surface = None
        self.boxes = {
            'all': set(),
            'highlighted': set(),
            'mouse_over': None,
        }

    def hide(self):
        self.unload_content()
        self.visible = False

    def draw_border(self, cairo_context):
        border = self.BORDER_BASIC
        if self.boxes['highlighted']:
            border = self.BORDER_HIGHLIGHTED

        border_width = border[0]
        border_color = border[1]

        cairo_context.save()
        try:
            cairo_context.set_source_rgb(border_color[0], border_color[1],
                                         border_color[2])
            cairo_context.rectangle(self.position[0] - self.canvas.offset[0]
                                    - border_width,
                                    self.position[1] - self.canvas.offset[1]
                                    - border_width,
                                    self.size[0] + (2 * border_width),
                                    self.size[1] + (2 * border_width))
            cairo_context.clip()
            cairo_context.paint()
        finally:
            cairo_context.restore()

    def draw_tmp_area(self, cairo_context):
        cairo_context.save()
        try:
            cairo_context.set_source_rgb(self.TMP_AREA[0],
                                         self.TMP_AREA[1],
                                         self.TMP_AREA[2])
            cairo_context.rectangle(self.position[0] - self.canvas.offset[0],
                                    self.position[1] - self.canvas.offset[1],
                                    self.size[0], self.size[1])
            cairo_context.clip()
            cairo_context.paint()
        finally:
            cairo_context.restore()

    def _get_factors(self):
        return (
            (float(self._size[0]) / self.max_size[0]),
            (float(self._size[1]) / self.max_size[1]),
        )

    def _get_real_box(self, box):
        (x_factor, y_factor) = self._get_factors()

        ((a, b), (c, d)) = box.position
        (w, h) = (c - a, d - b)

        a *= x_factor
        b *= y_factor
        w *= x_factor
        h *= y_factor

        a += self.position[0]
        b += self.position[1]
        a -= self.canvas.offset[0]
        b -= self.canvas.offset[1]

        return (int(a), int(b), int(w), int(h))

    def draw_boxes(self, cairo_context, boxes, color):
        for box in boxes:
            (a, b, w, h) = self._get_real_box(box)
            cairo_context.save()
            try:
                cairo_context.set_source_rgb(color[0], color[1], color[2])
                cairo_context.set_line_width(self.LINE_WIDTH)
                cairo_context.rectangle(a, b, w, h)
                cairo_context.stroke()
            finally:
                cairo_context.restore()

    def draw_box_txt(self, cairo_context, box):
        (a, b, w, h) = self._get_real_box(box)

        cairo_context.save()
        try:
            cairo_context.set_source_rgb(1.0, 1.0, 1.0)
            cairo_context.rectangle(a, b, w, h)
            cairo_context.clip()
            cairo_context.paint()
        finally:
            cairo_context.restore()

        cairo_context.save()
        try:
            cairo_context.translate(a, b)
            cairo_context.set_source_rgb(0.0, 0.0, 0.0)

            layout = PangoCairo.create_layout(cairo_context)
            layout.set_text(box.content, -1)

            txt_size = layout.get_size()
            if 0 in txt_size:
                return
            txt_factor = min(
                float(w) * Pango.SCALE / txt_size[0],
                float(h) * Pango.SCALE / txt_size[1],
            )

            cairo_context.scale(txt_factor, txt_factor)

            PangoCairo.update_layout(cairo_context, layout)
            PangoCairo.show_layout(cairo_context, layout)
        finally:
            cairo_context.restore()

    def _get_button_position(self, b_position):
        position = self.position
        size = self.size

        x = b_position[0]
        y = b_position[1]
        if x < 0:
            x = size[0] + x
        if y < 0:
            y = size[1] + y
        x += position[0] - self.canvas.offset[0]
        y += position[1] - self.canvas.offset[1]

        # keep the buttons visible
        if (y < b_position[1]):
            y = b_position[1]

        return (x, y)

    def draw_editor_buttons(self, cairo_context):
        buttons = self.editor_buttons[self.editor_state]
        for (b_position, button, callback, tooltip) in buttons:
            (x, y) = self._get_button_position(b_position)

            cairo_context.save()
            try:
                cairo_context.set_source_rgb(0.0, 0.0, 0.0)
                cairo_context.set_line_width(1.0)
                cairo_context.rectangle(x - 1, y - 1,
                                        self.BUTTON_SIZE + 2,
                                        self.BUTTON_SIZE + 2)
                cairo_context.stroke()
            finally:
                cairo_context.restore()

            cairo_context.save()
            try:
                cairo_context.set_source_rgb(
                    self.BUTTON_BACKGROUND[0], self.BUTTON_BACKGROUND[1],
                    self.BUTTON_BACKGROUND[2])
                cairo_context.rectangle(x, y,
                                        self.BUTTON_SIZE,
                                        self.BUTTON_SIZE)
                cairo_context.clip()
                cairo_context.paint()

                Gdk.cairo_set_source_pixbuf(cairo_context, button, x, y)
                cairo_context.rectangle(
                    x, y, self.BUTTON_SIZE, self.BUTTON_SIZE)
                cairo_context.clip()
                cairo_context.paint()
            finally:
                cairo_context.restore()

    def draw_editor_button_tooltip(self, cairo_context):
        if self.mouse_over_button:
            (b_position, button, callback, tooltip) = self.mouse_over_button
            (x, y) = self._get_button_position(b_position)
            x -= self.TOOLTIP_LENGTH + 2

            cairo_context.save()
            try:
                cairo_context.set_source_rgb(
                    self.BUTTON_BACKGROUND[0], self.BUTTON_BACKGROUND[1],
                    self.BUTTON_BACKGROUND[2])
                cairo_context.rectangle(x, y + 5,
                                        self.TOOLTIP_LENGTH,
                                        self.BUTTON_SIZE - 10)
                cairo_context.clip()
                cairo_context.paint()

                cairo_context.translate(
                    x + 5,
                    y + ((self.BUTTON_SIZE - self.FONT_SIZE) / 2))
                cairo_context.set_source_rgb(0.0, 0.0, 0.0)

                layout = PangoCairo.create_layout(cairo_context)
                layout.set_text(tooltip, -1)

                txt_size = layout.get_size()
                if 0 in txt_size:
                    return
                txt_factor = min(
                    float(self.TOOLTIP_LENGTH - 10) * Pango.SCALE / txt_size[0],
                    float(self.FONT_SIZE) * Pango.SCALE / txt_size[1],
                )
                cairo_context.scale(txt_factor, txt_factor)
                PangoCairo.update_layout(cairo_context, layout)
                PangoCairo.show_layout(cairo_context, layout)
            finally:
                cairo_context.restore()

    def draw_mask(self, cairo_ctx, mask_color):
        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(mask_color[0], mask_color[1],
                                      mask_color[2], mask_color[3])
            cairo_ctx.rectangle(self.position[0] - self.canvas.offset[0],
                                self.position[1] - self.canvas.offset[1],
                                self.size[0], self.size[1])
            cairo_ctx.clip()
            cairo_ctx.paint()
        finally:
            cairo_ctx.restore()

    def draw(self, cairo_context):
        should_be_visible = self.compute_visibility(
            self.canvas.offset, self.canvas.size,
            self.position, self.size)
        if should_be_visible and not self.visible:
            self.load_content()
        elif not should_be_visible and self.visible:
            self.unload_content()
        self.visible = should_be_visible

        if not self.visible:
            return

        if (self.show_border
                and (self.mouse_over or self.boxes['highlighted'])):
            self.draw_border(cairo_context)

        if not self.surface:
            self.draw_tmp_area(cairo_context)
        else:
            self.draw_surface(cairo_context,
                              self.surface, self.position,
                              self.size, angle=self.angle)

        if self.show_all_boxes:
            self.draw_boxes(cairo_context,
                            self.boxes['all'], color=(0.0, 0.0, 0.5))
        if self.boxes["mouse_over"]:
            self.draw_boxes(cairo_context,
                            [self.boxes['mouse_over']], color=(0.0, 0.0, 1.0))
            self.draw_box_txt(cairo_context,
                              self.boxes['mouse_over'])
        if self.show_boxes:
            self.draw_boxes(cairo_context,
                            self.boxes['highlighted'], color=(0.0, 0.85, 0.0))

        if self.enable_editor and self.mouse_over:
            self.draw_editor_buttons(cairo_context)
            self.draw_editor_button_tooltip(cairo_context)

        if self.is_drag_source:
            self.draw_mask(cairo_context, (0.0, 0.0, 0.0, 0.15))

    def _get_box_at(self, x, y):
        for box in self.boxes["all"]:
            if (x >= box.position[0][0]
                    and x <= box.position[1][0]
                    and y >= box.position[0][1]
                    and y <= box.position[1][1]):
                return box
        return None

    def redraw(self, extra_border=0):
        border = self.BORDER_BASIC
        if self.boxes['highlighted']:
            border = self.BORDER_HIGHLIGHTED

        border_width = max(border[0], extra_border)

        position = self.relative_position
        position = (position[0] - border_width,
                    position[1] - border_width)

        size = self.relative_size
        size = (size[0] + (2 * border_width),
                size[1] + (2 * border_width))

        self.canvas.redraw((position, size))

    def set_drag_enabled(self, drag):
        self.drag_enabled = drag
        if drag:
            self.canvas.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [],
                                        Gdk.DragAction.MOVE)
            self.canvas.drag_source_add_text_targets()
        else:
            self.canvas.drag_source_unset()

    def _on_mouse_motion(self, event):
        position = self.position
        size = self.size

        event_x = event.x
        event_y = event.y

        must_redraw = False
        mouse_over_button = None

        inside = (event_x >= position[0]
                  and event_x < position[0] + size[0]
                  and event_y >= position[1]
                  and event_y < position[1] + size[1])

        if self.mouse_over != inside:
            self.set_drag_enabled(
                inside and self.page.doc.can_edit and self.drag_enabled
            )

            self.mouse_over = inside
            must_redraw = True

        buttons = self.editor_buttons[self.editor_state]
        for button in buttons:
            (b_position, b_pix, callback, tooltip) = button
            (x, y) = self._get_button_position(b_position)
            x += self.canvas.offset[0]
            y += self.canvas.offset[1]
            if (x <= event_x
                    and event_x <= x + self.BUTTON_SIZE
                    and y <= event_y
                    and event_y <= y + self.BUTTON_SIZE):
                mouse_over_button = button
                break

        if self.mouse_over_button != mouse_over_button:
            self.mouse_over_button = mouse_over_button
            must_redraw = True

        if inside:
            (x_factor, y_factor) = self._get_factors()
            # position on the whole page image
            (x, y) = (event_x - position[0], event_y - position[1])
            (x, y) = (
                x / x_factor,
                y / y_factor,
            )

            box = self._get_box_at(x, y)
            if box != self.boxes["mouse_over"]:
                # redraw previous box to make the border disappear
                if not must_redraw and self.boxes["mouse_over"]:
                    box_pos = self._get_real_box(self.boxes["mouse_over"])
                    self.canvas.redraw(((box_pos[0] - self.LINE_WIDTH,
                                        box_pos[1] - self.LINE_WIDTH),
                                        (box_pos[2] + (2 * self.LINE_WIDTH),
                                        box_pos[2] + (2 * self.LINE_WIDTH))))

                self.boxes["mouse_over"] = box

                # draw new one to make the border appear
                if not must_redraw and box:
                    box_pos = self._get_real_box(box)
                    self.canvas.redraw(((box_pos[0] - self.LINE_WIDTH,
                                        box_pos[1] - self.LINE_WIDTH),
                                        (box_pos[2] + (2 * self.LINE_WIDTH),
                                        box_pos[2] + (2 * self.LINE_WIDTH))))

        if must_redraw:
            self.redraw()
            return

    def _on_mouse_button_release(self, event):
        position = self.position
        size = self.size

        inside = (event.x >= position[0]
                  and event.x < (position[0] + size[0])
                  and event.y >= position[1]
                  and event.y < (position[1] + size[1]))

        if not inside:
            return

        click_x = event.x
        click_y = event.y

        # check first if the user clicked on a button
        if self.enable_editor:
            buttons = self.editor_buttons[self.editor_state]
            for (b_position, button_pix, callback, tooltip) in buttons:
                (button_x, button_y) = self._get_button_position(b_position)
                button_x += self.canvas.offset[0]
                button_y += self.canvas.offset[1]
                if (button_x <= click_x
                        and button_y <= click_y
                        and click_x <= button_x + self.BUTTON_SIZE
                        and click_y <= button_y + self.BUTTON_SIZE):
                    callback()
                    return

        if self.editor_state == "before":
            self.emit('page-selected')
            return

        return

    def _on_edit_start(self):
        logger.info("Starting page editing")
        self.set_drag_enabled(False)
        self.editor_state = "during"
        self.mouse_over_button = self.editor_buttons['during'][0]
        self.redraw()

    def _on_edit_crop(self):
        # TODO(JFlesch): support rotation + crop at the same time
        self.angle = 0
        if not self.editor_grips:
            logger.info("Starting page cropping")
            self.editor_grips = ImgGripHandler(
                img_drawer=self, canvas=self.canvas)
            self.editor_grips.visible = True
        else:
            logger.info("Stopping page cropping")
            self.editor_grips.destroy()
            self.editor_grips = None

    def _on_edit_counterclockwise(self):
        logger.info("Rotating -90")
        self.angle -= 90
        self.angle %= 360
        self.canvas.redraw()

    def _on_edit_clockwise(self):
        logger.info("Rotating 90")
        self.angle += 90
        self.angle %= 360
        self.canvas.redraw()

    def _on_edit_done(self):
        self.set_drag_enabled(True)
        if self.editor_grips:
            logger.info("Stopping page cropping")
            self.editor_grips.destroy()
            self.editor_grips = None
        self.editor_state = "before"
        self.angle = 0
        self.hide()
        self.canvas.redraw()

    def _on_edit_cancel(self):
        logger.info("Page edition canceled")
        self.mouse_over_button = self.editor_buttons['before'][0]
        self._on_edit_done()

    def _on_edit_apply(self):
        actions = []
        if self.angle != 0:
            actions.append(PageRotationAction(self.angle))
        if self.editor_grips:
            img_real_size = self.max_size
            current_size = self.size
            zoom_level = float(img_real_size[0]) / float(current_size[0])
            logger.info("Zoom level: %f" % zoom_level)
            coords = self.editor_grips.get_coords()
            coords = (
                (int(coords[0][0] * zoom_level),
                 int(coords[0][1] * zoom_level)),
                (int(coords[1][0] * zoom_level),
                 int(coords[1][1] * zoom_level)),
            )
            actions.append(PageCuttingAction(coords))
        logger.info("Page edition applied: %s"
                    % ", ".join([str(a) for a in actions]))
        self.emit("page-edited", actions)
        self._on_edit_done()

    def _on_delete(self):
        self.emit("page-deleted")


GObject.type_register(PageDrawer)


class PageDropHandler(Drawer):
    LINE_BORDERS = 10
    LINE_WIDTH = 3
    LINE_COLOR = (0.0, 0.8, 1.0, 1.0)

    layer = Drawer.BOX_LAYER

    def __init__(self, main_win):
        self.__main_win = main_win

        # None = means the new page will be the first one
        self.active = False
        self.target_previous_page_drawer = None

    def set_canvas(self, canvas):
        super(PageDropHandler, self).set_canvas(canvas)
        canvas = self.__main_win.img['canvas']
        canvas.connect(self, "drag-motion", self._on_drag_motion)
        canvas.connect(self, "drag-leave", self._on_drag_leave)
        canvas.connect(self, "drag-drop", self._on_drag_drop)
        canvas.connect(self, "drag-data-received", self._on_drag_data_received)

    def distance(self, mouse_x, mouse_y,
                 page_drawer_position, page_drawer_size):
        x = page_drawer_position[0] + page_drawer_size[0]
        y = page_drawer_position[1] + (page_drawer_size[1] / 2)

        x -= mouse_x
        y -= mouse_y

        return math.hypot(x, y)

    def _on_drag_motion(self, canvas, drag_context, mouse_x, mouse_y, time):
        Gdk.drag_status(drag_context, Gdk.DragAction.MOVE, time)
        # issue a redraw order on our current position
        self.redraw()

        self.active = True

        mouse_x += self.canvas.offset[0]
        mouse_y += self.canvas.offset[1]

        distances = [
            (
                self.distance(mouse_x, mouse_y, drawer.position, drawer.size),
                drawer
            )
            for drawer in self.__main_win.page_drawers
        ]

        # we must to provide a position for a fake page -1
        first_page_position = (0, 0)
        first_page_size = (0, 0)
        if len(self.__main_win.page_drawers) > 0:
            first_page_position = self.__main_win.page_drawers[0].position
            first_page_size = self.__main_win.page_drawers[0].size
        first_page_position = (0, first_page_position[1])

        distances.append(
            (
                self.distance(mouse_x, mouse_y,
                              first_page_position, first_page_size),
                None
            )
        )
        distances.sort()

        if len(distances) <= 0:
            self.target_previous_page_drawer = None
        else:
            self.target_previous_page_drawer = distances[0][1]

        # issue a redraw order on our new position
        GLib.idle_add(self.redraw)
        return True

    def _on_drag_leave(self, canvas, drag_context, time):
        # issue a redraw order on our current position
        self.active = False
        self.redraw()

    def _on_drag_drop(self, canvas, drag_context, x, y, time):
        # issue a redraw order on our current position
        self.active = False
        self.redraw()
        return True

    def _on_drag_data_received(self, canvas, drag_context,
                               x, y, data, info, time):
        # issue a redraw order on our current position
        self.active = False

        page_id = data.get_text()
        src_page = self.__main_win.docsearch.get(page_id)
        dst_doc = self.__main_win.doc

        if self.target_previous_page_drawer:
            dst_page_nb = self.target_previous_page_drawer.page.page_nb + 1
        else:
            dst_page_nb = 0

        logger.info("Drag-n-drop page: %s --> %s %d"
                    % (str(src_page), str(dst_doc), dst_page_nb))

        if ((dst_page_nb == src_page.page_nb
                or dst_page_nb == src_page.page_nb + 1)
                and dst_doc.docid == src_page.doc.docid):
            logger.warn("Drag-n-drop: Dropped to the original position")
            drag_context.finish(False, False, time)  # success = True
            return

        # pop the page ..
        boxes = src_page.boxes
        img = src_page.img
        src_page.destroy()

        if (dst_doc.docid == src_page.doc.docid
                and dst_page_nb > src_page.page_nb):
            dst_page_nb -= 1

        # .. and re-add it
        dst_page = dst_doc.insert_page(img, boxes, dst_page_nb)

        drag_context.finish(True, True, time)  # success = True
        self.__main_win.show_page(dst_page, force_refresh=True)
        self.__main_win.upd_index({src_page.doc, dst_page.doc})

    def set_enabled(self, enabled):
        canvas = self.__main_win.img['canvas']

        if not enabled:
            canvas.drag_dest_unset()
        else:
            canvas.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.MOVE)
            canvas.drag_dest_add_text_targets()

    def get_position(self):
        if not self.target_previous_page_drawer:
            return (0, 0)
        position = self.target_previous_page_drawer.position
        size = self.target_previous_page_drawer.size
        return (
            (position[0] + size[0] + self.LINE_BORDERS),
            (position[1] - self.LINE_BORDERS)
        )

    position = property(get_position)

    def get_size(self):
        if not self.target_previous_page_drawer:
            return (2 * self.LINE_BORDERS, 50)
        size = self.target_previous_page_drawer.size
        return (
            (2 * self.LINE_BORDERS),
            (size[1] + (2 * self.LINE_BORDERS))
        )

    size = property(get_size)

    def do_draw(self, cairo_ctx):
        if not self.active:
            return

        position = self.position
        size = self.size

        position = (
            position[0] - self.canvas.offset[0],
            position[1] - self.canvas.offset[1]
        )

        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgba(
                self.LINE_COLOR[0], self.LINE_COLOR[1],
                self.LINE_COLOR[2], self.LINE_COLOR[3])
            cairo_ctx.set_line_width(self.LINE_WIDTH)

            cairo_ctx.move_to(position[0] + self.LINE_BORDERS,
                              position[1])
            cairo_ctx.line_to(position[0] + self.LINE_BORDERS,
                              position[1] + size[1])
            cairo_ctx.stroke()

            cairo_ctx.move_to(position[0],
                              position[1] + self.LINE_BORDERS)
            cairo_ctx.line_to(position[0] + (2 * self.LINE_BORDERS),
                              position[1] + self.LINE_BORDERS)
            cairo_ctx.stroke()

            cairo_ctx.move_to(position[0],
                              position[1] + size[1] - self.LINE_BORDERS)
            cairo_ctx.line_to(position[0] + (2 * self.LINE_BORDERS),
                              position[1] + size[1] - self.LINE_BORDERS)
            cairo_ctx.stroke()
        finally:
            cairo_ctx.restore()
