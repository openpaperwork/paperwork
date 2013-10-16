from paperwork.frontend.util.canvas.drawers import Drawer

from gi.repository import GLib
from gi.repository import GObject

from paperwork.backend.util import image2surface
from paperwork.frontend.util.canvas.drawers import Drawer
from paperwork.frontend.util.jobs import Job
from paperwork.frontend.util.jobs import JobFactory
from paperwork.frontend.util.jobs import JobScheduler


class JobPageLoader(Job):
    can_stop = False
    priority = 350

    __gsignals__ = {
        'page-loading-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'page-loading-img': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_PYOBJECT,)),
        'page-loading-boxes': (GObject.SignalFlags.RUN_LAST, None,
                               (GObject.TYPE_PYOBJECT,)),  # array of boxes
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
        # TODO(Jflesch): boxes
        return job


class PageDrawer(Drawer):
    layer = Drawer.IMG_LAYER

    def __init__(self, position, page,
                 job_page_loader_factory,
                 job_scheduler):
        self.position = position
        self.page = page
        self.size = page.size
        self.max_size = self.size
        self.surface = None
        self.visible = False
        self.loading = False

        self.job_page_loader_factory = job_page_loader_factory
        self.job_scheduler = job_scheduler

    def set_size_ratio(self, factor):
        self.size = (int(factor * self.max_size[0]),
                     int(factor * self.max_size[1]))

    def load_img(self):
        if self.loading:
            return
        self.loading = True
        job = self.job_page_loader_factory.make(self, self.page)
        self.job_scheduler.schedule(job)

    def on_page_loading_img(self, page, surface):
        self.loading = False
        if not self.visible:
            return
        self.surface = surface
        self.canvas.redraw()

    def unload_img(self):
        del(self.surface)

    def hide(self):
        self.unload_img()
        self.visible = False

    def do_draw(self, cairo_context, canvas_offset, canvas_visible_size):
        should_be_visible = self.compute_visibility(
            canvas_offset, canvas_visible_size,
            self.position, self.size)
        if should_be_visible and not self.visible:
            self.load_img()
        elif not should_be_visible and self.visible:
            self.unload_img()
        self.visible = should_be_visible

        if not self.visible or not self.surface:
            return

        self.draw_surface(cairo_context, canvas_offset, canvas_visible_size,
                          self.surface, self.position, self.size)
