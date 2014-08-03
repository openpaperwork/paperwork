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

import cairo
import math
from gi.repository import GObject
from gi.repository import Gtk


class CellRendererLabels(Gtk.CellRenderer):
    LABEL_HEIGHT = 25
    LABEL_SPACING = 3
    LABEL_TEXT_SIZE = 13
    LABEL_CORNER_RADIUS = 10

    labels = GObject.property(type=object, default=None,
                              flags=GObject.PARAM_READWRITE)
    highlight = GObject.property(type=bool, default=False,
                                 flags=GObject.PARAM_READWRITE)

    def __init__(self):
        Gtk.CellRenderer.__init__(self)

    def do_get_size(self, widget, cell_area):
        if self.labels is None or len(self.labels) == 0:
            return (0, 0, 0, 0)
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        width = 50  # meh, not really used
        height = len(self.labels) * (self.LABEL_HEIGHT + self.LABEL_SPACING)
        return (xpad, ypad, width+(2*ypad), height+(2*ypad))

    @staticmethod
    def _rectangle_rounded(cairo_ctx, area, radius):
        (x, y, w, h) = area
        cairo_ctx.new_sub_path()
        cairo_ctx.arc(x + w - radius, y + radius, radius,
                      -1.0 * math.pi / 2, 0)
        cairo_ctx.arc(x + w - radius, y + h - radius, radius, 0, math.pi / 2)
        cairo_ctx.arc(x + radius, y + h - radius, radius,
                      math.pi / 2, math.pi)
        cairo_ctx.arc(x + radius, y + radius, radius, math.pi,
                      3.0 * math.pi / 2)
        cairo_ctx.close_path()

    def do_render(self, cairo_ctx, widget,
                  bg_area_gdk_rect, cell_area_gdk_rect,
                  flags):
        if self.labels is None or len(self.labels) == 0:
            return

        txt_offset = (self.LABEL_HEIGHT - self.LABEL_TEXT_SIZE) / 2
        cairo_ctx.set_font_size(self.LABEL_TEXT_SIZE)

        if not self.highlight:
            cairo_ctx.select_font_face("", cairo.FONT_SLANT_NORMAL,
                                       cairo.FONT_WEIGHT_NORMAL)
        else:
            cairo_ctx.select_font_face("", cairo.FONT_SLANT_NORMAL,
                                       cairo.FONT_WEIGHT_BOLD)

        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        (x, y, w) = (cell_area_gdk_rect.x + xpad,
                     cell_area_gdk_rect.y + ypad,
                     cell_area_gdk_rect.width - (2*xpad))

        for label_idx in xrange(0, len(self.labels)):
            label = self.labels[label_idx]

            (label_x, label_y, label_w, label_h) = (
                x, y + (label_idx * (self.LABEL_HEIGHT + self.LABEL_SPACING)),
                w, self.LABEL_HEIGHT
            )

            # background rectangle
            bg = label.get_rgb_bg()
            cairo_ctx.set_source_rgb(bg[0], bg[1], bg[2])
            cairo_ctx.set_line_width(1)
            self._rectangle_rounded(cairo_ctx,
                                    (label_x, label_y, label_w, label_h),
                                    self.LABEL_CORNER_RADIUS)
            cairo_ctx.fill()

            # foreground text
            fg = label.get_rgb_fg()
            cairo_ctx.set_source_rgb(fg[0], fg[1], fg[2])
            cairo_ctx.move_to(label_x + self.LABEL_CORNER_RADIUS,
                              label_y + self.LABEL_HEIGHT - txt_offset)
            cairo_ctx.show_text(label.name)


GObject.type_register(CellRendererLabels)
