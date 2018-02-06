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

from gi.repository import GObject

from paperwork.frontend.util.canvas import Canvas


class Animator(GObject.GObject):
    __gsignals__ = {
        'animator-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'animator-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self,
                 drawer,
                 attr_name, attr_values,  # one value per canvas tick
                 canvas=None):
        GObject.GObject.__init__(self)
        self.drawer = drawer
        self.attr_name = attr_name
        self.attr_values = attr_values
        self.canvas = canvas
        self.started = False
        self.stopped = False

        self.previous_pos = self.drawer.relative_position
        self.previous_size = self.drawer.relative_size

    def set_canvas(self, canvas):
        self.canvas = canvas

    def on_tick(self):
        if len(self.attr_values) <= 0:
            if not self.stopped:
                self.stopped = True
                self.emit('animator-end')
            return
        if not self.started:
            self.started = True
            self.emit('animator-start')
        setattr(self.drawer, self.attr_name, self.attr_values[0])
        self.attr_values = self.attr_values[1:]

        self.canvas.redraw((self.previous_pos, self.previous_size))
        self.previous_pos = self.drawer.relative_position
        self.previous_size = self.drawer.relative_size
        self.canvas.redraw((self.previous_pos, self.previous_size))


class LinearSimpleAnimator(Animator):

    def __init__(self, drawer,
                 target_value,
                 time_length,  # ms
                 attr_name='angle',
                 canvas=None):
        nb_values = int(time_length / Canvas.TICK_INTERVAL)
        assert(nb_values)
        value_intervals = (
            (target_value - getattr(drawer, attr_name)) / nb_values
        )
        values = [
            getattr(drawer, attr_name) + (i * value_intervals)
            for i in range(0, nb_values + 1)
        ]
        if values[-1] != target_value:
            values.append(target_value)
        Animator.__init__(self, drawer, attr_name, values, canvas)


GObject.type_register(LinearSimpleAnimator)


class LinearCoordAnimator(Animator):

    def __init__(self, drawer,
                 target_coord,
                 time_length,  # ms
                 attr_name='position',
                 canvas=None):
        nb_coords = int(time_length / Canvas.TICK_INTERVAL)
        assert(nb_coords)
        pos_intervals = (
            (target_coord[0] - getattr(drawer, attr_name)[0]) / nb_coords,
            (target_coord[1] - getattr(drawer, attr_name)[1]) / nb_coords,
        )
        coords = [
            (getattr(drawer, attr_name)[0] + (i * pos_intervals[0]),
             getattr(drawer, attr_name)[1] + (i * pos_intervals[1]))
            for i in range(0, nb_coords + 1)
        ]
        Animator.__init__(self, drawer, attr_name, coords, canvas)


GObject.type_register(LinearCoordAnimator)
