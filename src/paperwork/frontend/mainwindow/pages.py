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

import threading

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Pango
from gi.repository import PangoCairo
import PIL.Image

from paperwork.backend.common.page import BasicPage
from paperwork.backend.util import image2surface
from paperwork.backend.util import split_words
from paperwork.frontend.util.canvas.animations import SpinnerAnimation
from paperwork.frontend.util.canvas.drawers import Drawer
from paperwork.frontend.util.jobs import Job
from paperwork.frontend.util.jobs import JobFactory


class JobPageImgLoader(Job):
    can_stop = False
    priority = 500

    __gsignals__ = {
        'page-loading-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'page-loading-img': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_PYOBJECT,)),
        'page-loading-done': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, factory, job_id, page, size, use_thumbnail=False):
        Job.__init__(self, factory, job_id)
        self.page = page
        self.size = size
        self.use_thumbnail = use_thumbnail

    def do(self):
        self.emit('page-loading-start')
        try:
            if not self.use_thumbnail:
                img = self.page.img
            else:
                img = self.page.get_thumbnail(BasicPage.DEFAULT_THUMB_WIDTH,
                                              BasicPage.DEFAULT_THUMB_HEIGHT)
            if self.size != img.size:
                img = img.resize(self.size, PIL.Image.ANTIALIAS)
            img.load()
            self.emit('page-loading-img', image2surface(img))

        finally:
            self.emit('page-loading-done')


GObject.type_register(JobPageImgLoader)


class JobFactoryPageImgLoader(JobFactory):

    def __init__(self):
        JobFactory.__init__(self, "PageImgLoader")

    def make(self, drawer, page, size, use_thumbnail=False):
        job = JobPageImgLoader(self, next(self.id_generator), page, size,
                               use_thumbnail)
        job.connect('page-loading-img',
                    lambda job, img:
                    GLib.idle_add(drawer.on_page_loading_img,
                                  job.page, img))
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
                self.__cond.wait(1.0)
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


class PageDrawer(Drawer, GObject.GObject):
    layer = Drawer.IMG_LAYER
    LINE_WIDTH = 1.0
    MARGIN = 25
    BORDER = (5, (0.85, 0.85, 0.85))
    TMP_AREA = (0.85, 0.85, 0.85)

    __gsignals__ = {
        'page-selected': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, page,
                 job_factories,
                 job_schedulers,
                 previous_page_drawer=None,
                 show_boxes=True,
                 show_all_boxes=False,
                 show_border=False,
                 use_thumbnail=False,
                 sentence=u""):
        GObject.GObject.__init__(self)
        Drawer.__init__(self)

        self.max_size = page.size
        self.page = page
        self.show_boxes = show_boxes
        self.show_all_boxes = show_all_boxes
        self.show_border = show_border
        self.has_border = False
        self.use_thumbnail = use_thumbnail
        self.previous_page_drawer = previous_page_drawer

        self.surface = None
        self.boxes = {
            'all': [],
            'highlighted': [],
            'mouse_over': None,
        }
        self.sentence = sentence
        self.visible = False
        self.loading = False

        self.factories = job_factories
        self.schedulers = job_schedulers

        self._size = self.max_size
        self._position = (0, 0)
        self.spinner = SpinnerAnimation((0, 0))
        self.upd_spinner_position()

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
        canvas.connect("absolute-motion-notify-event", lambda canvas, event:
                       GLib.idle_add(self._on_mouse_motion, event))
        canvas.connect("absolute-button-release-event",
                       lambda canvas, event:
                       GLib.idle_add(self._on_mouse_button_release, event))
        canvas.connect("size-allocate", self._on_size_allocate_cb)

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
        if size != self._size:
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
                                                     self.size,
                                                     self.use_thumbnail)
        self.schedulers['page_img_loader'].schedule(job)

    def on_page_loading_img(self, page, surface):
        if self.loading:
            self.canvas.remove_drawer(self.spinner)
            self.loading = False
        if not self.visible:
            return
        self.surface = surface
        self.redraw()
        if len(self.boxes['all']) <= 0 and self.show_boxes:
            job = self.factories['page_boxes_loader'].make(self, self.page)
            self.schedulers['page_boxes_loader'].schedule(job)

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
        self.boxes['all'] = all_boxes
        self.reload_boxes()

    def unload_content(self):
        if self.loading:
            self.canvas.remove_drawer(self.spinner)
            self.loading = False
        if self.surface is not None:
            del(self.surface)
            self.surface = None
        self.boxes = {
            'all': [],
            'highlighted': [],
            'mouse_over': None,
        }

    def hide(self):
        self.unload_content()
        self.visible = False

    def draw_border(self, cairo_context):
        border_width = self.BORDER[0]
        border_color = self.BORDER[1]

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

        if self.has_border:
            self.draw_border(cairo_context)

        if not self.surface:
            self.draw_tmp_area(cairo_context)
        else:
            self.draw_surface(cairo_context,
                              self.surface, self.position,
                              self.size)

        if self.show_all_boxes:
            self.draw_boxes(cairo_context,
                            self.boxes['all'], color=(0.0, 0.0, 0.5))
        if self.boxes["mouse_over"]:
            self.draw_boxes(cairo_context,
                            [self.boxes['mouse_over']], color=(0.0, 0.0, 1.0))
            self.draw_box_txt(cairo_context,
                              self.boxes['mouse_over'])
        self.draw_boxes(cairo_context,
                        self.boxes['highlighted'], color=(0.0, 0.85, 0.0))

    def _get_box_at(self, x, y):
        for box in self.boxes["all"]:
            if (x >= box.position[0][0]
                    and x <= box.position[1][0]
                    and y >= box.position[0][1]
                    and y <= box.position[1][1]):
                return box
        return None

    def redraw(self):
        border_width = self.BORDER[0]

        position = self.relative_position
        position = (position[0] - border_width,
                    position[1] - border_width)

        size = self.relative_size
        size = (size[0] + (2 * border_width),
                size[1] + (2 * border_width))

        self.canvas.redraw((position, size))

    def _on_mouse_motion(self, event):
        position = self.position
        size = self.size

        inside = (event.x >= position[0]
                  and event.x < (position[0] + size[0])
                  and event.y >= position[1]
                  and event.y < (position[1] + size[1]))

        if self.show_border and self.has_border != inside:
            self.has_border = inside
            self.redraw()

        if not inside:
            return

        (x_factor, y_factor) = self._get_factors()
        # position on the whole page image
        (x, y) = (
            (event.x - position[0]) / x_factor,
            (event.y - position[1]) / y_factor,
        )

        box = self._get_box_at(x, y)
        if box != self.boxes["mouse_over"]:
            # redraw previous box
            if self.boxes["mouse_over"]:
                box_pos = self._get_real_box(self.boxes["mouse_over"])
                self.canvas.redraw(((box_pos[0] - self.LINE_WIDTH,
                                     box_pos[1] - self.LINE_WIDTH),
                                    (box_pos[2] + (2 * self.LINE_WIDTH),
                                     box_pos[2] + (2 * self.LINE_WIDTH))))

            # draw new one
            self.boxes["mouse_over"] = box
            if box:
                box_pos = self._get_real_box(box)
                self.canvas.redraw(((box_pos[0] - self.LINE_WIDTH,
                                     box_pos[1] - self.LINE_WIDTH),
                                    (box_pos[2] + (2 * self.LINE_WIDTH),
                                     box_pos[2] + (2 * self.LINE_WIDTH))))

    def _on_mouse_button_release(self, event):
        position = self.position
        size = self.size

        inside = (event.x >= position[0]
                  and event.x < (position[0] + size[0])
                  and event.y >= position[1]
                  and event.y < (position[1] + size[1]))

        if not inside:
            return

        self.emit('page-selected')

GObject.type_register(PageDrawer)
