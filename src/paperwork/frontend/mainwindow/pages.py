from paperwork.frontend.util.canvas.drawers import Drawer

from gi.repository import GLib
from gi.repository import GObject

from paperwork.backend.util import image2surface
from paperwork.frontend.util.canvas.drawers import Drawer
from paperwork.frontend.util.canvas.drawers import SpinnerDrawer
from paperwork.frontend.util.jobs import Job
from paperwork.frontend.util.jobs import JobFactory
from paperwork.frontend.util.jobs import JobScheduler


class JobPageLoader(Job):
    can_stop = False
    priority = 500

    __gsignals__ = {
        'page-loading-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'page-loading-img': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_PYOBJECT,)),
        'page-loading-done': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, factory, job_id, page):
        Job.__init__(self, factory, job_id)
        self.page = page

    def do(self):
        self.emit('page-loading-start')
        try:
            img = self.page.img
            img.load()
            self.emit('page-loading-img', image2surface(img))

        finally:
            self.emit('page-loading-done')

GObject.type_register(JobPageLoader)


class JobFactoryPageLoader(JobFactory):
    def __init__(self):
        JobFactory.__init__(self, "PageLoader")

    def make(self, drawer, page):
        job = JobPageLoader(self, next(self.id_generator), page)
        job.connect('page-loading-img',
                    lambda job, img:
                    GLib.idle_add(drawer.on_page_loading_img,
                                  job.page, img))
        return job


class PageDrawer(Drawer):
    layer = Drawer.IMG_LAYER

    def __init__(self, position, page,
                 job_factories,
                 job_schedulers):
        Drawer.__init__(self)

        self.max_size = page.size
        self.page = page
        self.surface = None
        self.visible = False
        self.loading = False

        self.factories = job_factories
        self.schedulers = job_schedulers

        self._position = position
        self._size = self.max_size
        self.spinner = SpinnerDrawer((0, 0))
        self.upd_spinner_position()

    def on_tick(self):
        Drawer.on_tick(self)
        self.spinner.on_tick()

    def upd_spinner_position(self):
        self.spinner.position = (
            (self._position[0] + (self._size[0] / 2)
             - (SpinnerDrawer.ICON_SIZE / 2)),
            (self._position[1] + (self._size[1] / 2)
             - (SpinnerDrawer.ICON_SIZE / 2)),
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
        self._size = size
        self.upd_spinner_position()

    size = property(_get_size, _set_size)

    def set_size_ratio(self, factor):
        self.size = (int(factor * self.max_size[0]),
                     int(factor * self.max_size[1]))

    def load_img(self):
        if self.loading:
            return
        self.canvas.add_drawer(self.spinner)
        self.loading = True
        job = self.factories['page_loader'].make(self, self.page)
        self.schedulers['page_loader'].schedule(job)

    def on_page_loading_img(self, page, surface):
        if self.loading:
            self.canvas.remove_drawer(self.spinner)
            self.loading = False
        if not self.visible:
            return
        self.surface = surface
        self.canvas.redraw()

    def unload_img(self):
        if self.loading:
            self.canvas.remove_drawer(self.spinner)
            self.loading = False
        if self.surface is not None:
            del(self.surface)
            self.surface = None

    def hide(self):
        self.unload_img()
        self.visible = False

    def draw_tmp(self, cairo_context, canvas_offset, canvas_visible_size):
        cairo_context.save()
        try:
            cairo_context.set_source_rgb(0.85, 0.85, 0.85)
            cairo_context.rectangle(self.position[0] - canvas_offset[0],
                                    self.position[1] - canvas_offset[1],
                                    self.size[0], self.size[1])
            cairo_context.clip()
            cairo_context.paint()
        finally:
            cairo_context.restore()

    def draw(self, cairo_context, canvas_offset, canvas_visible_size):
        should_be_visible = self.compute_visibility(
            canvas_offset, canvas_visible_size,
            self.position, self.size)
        if should_be_visible and not self.visible:
            self.load_img()
        elif not should_be_visible and self.visible:
            self.unload_img()
        self.visible = should_be_visible

        if not self.visible:
            return

        if not self.surface:
            self.draw_tmp(cairo_context, canvas_offset, canvas_visible_size)
        else:
            self.draw_surface(cairo_context, canvas_offset,
                              canvas_visible_size,
                              self.surface, self.position,
                              self.size)
