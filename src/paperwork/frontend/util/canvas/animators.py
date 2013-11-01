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
            for i in xrange(0, nb_values + 1)
        ]
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
            for i in xrange(0, nb_coords + 1)
        ]
        Animator.__init__(self, drawer, attr_name, coords, canvas)


GObject.type_register(LinearCoordAnimator)
