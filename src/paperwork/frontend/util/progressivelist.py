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

import gettext
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from paperwork.frontend.util.jobs import Job
from paperwork.frontend.util.jobs import JobFactory


_ = gettext.gettext
logger = logging.getLogger(__name__)


class JobProgressiveList(Job):
    can_stop = True
    priority = 500

    def __init__(self, factory, id, progressive_list):
        Job.__init__(self, factory, id)
        self.__progressive_list = progressive_list
        self.can_run = True

    def do(self):
        self._wait(0.5)
        if not self.can_run:
            return
        GLib.idle_add(self.__progressive_list.display_extra)

    def stop(self, will_resume=True):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobProgressiveList)


class JobFactoryProgressiveList(JobFactory):

    def __init__(self, progressive_list):
        JobFactory.__init__(self, "Progressive List")
        self.progressive_list = progressive_list

    def make(self):
        return JobProgressiveList(self, next(self.id_generator),
                                  self.progressive_list)


class ProgressiveList(GObject.GObject):

    """
    We use GtkIconView to display documents and pages. However this widget
    doesn't like having too many elements to display: it keeps redrawing the
    list when the mouse goes over it --> with 600 documents, this may be
    quite long.

    So instead, we display only X elements. When the user scroll down,
    we add Y elements to the list, etc.
    """

    NB_EL_DISPLAYED_INITIALLY = 100
    NB_EL_DISPLAY_EXTRA_WHEN_LOWER_THAN = 0.85
    NB_EL_DISPLAYED_ADDITIONNAL = int(
        (1.0 - NB_EL_DISPLAY_EXTRA_WHEN_LOWER_THAN) * NB_EL_DISPLAYED_INITIALLY
    )

    __gsignals__ = {
        'lines-shown': (GObject.SignalFlags.RUN_LAST, None,
                        (GObject.TYPE_PYOBJECT, )),  # [(line_idx, obj), ... ]
    }

    def __init__(self, name,
                 scheduler,
                 default_thumbnail,
                 gui, scrollbars, model,
                 model_nb_columns, actions=[]):
        """
        Arguments:
            name --- Name of the progressive list (for verbose only)
            scheduler --- Job scheduler to use to schedule list extension jobs
            default_thumbnail --- default thumbnail to use until the new one is
                                    loaded
            gui --- list widget
            scrollbars --- scrollpane widget
            model -- liststore
            actions --- actions to disabled while updating the list
        """
        GObject.GObject.__init__(self)
        self.name = name
        self.scheduler = scheduler
        self.default_thumbnail = default_thumbnail
        self.actions = actions
        self.widget_gui = gui

        self.widget_scrollbars = scrollbars
        self._vadjustment = scrollbars.get_vadjustment()

        self.model = model
        self.model_content = []
        self.model_nb_columns = model_nb_columns

        self.nb_displayed = 0

        self._vadjustment.connect(
            "value-changed",
            lambda widget: GLib.idle_add(self.__on_scrollbar_moved))

        self.job_factory = JobFactoryProgressiveList(self)

    def set_model(self, model_content):
        self.model_content = model_content

        self.widget_gui.freeze_child_notify()
        self.widget_gui.set_model(None)
        try:
            self.model.clear()
            self.nb_displayed = 0
            self._display_up_to(self.NB_EL_DISPLAYED_INITIALLY)
        finally:
            self.widget_gui.freeze_child_notify()
            self.widget_gui.set_model(self.model)

    def display_extra(self):
        for action in self.actions:
            action.enabled = False
        try:
            selected = self.widget_gui.get_selected_items()
            if len(selected) <= 0:
                selected = -1
            else:
                selected = min([x.get_indices()[0] for x in selected])

            (first_visible, last_visible) = self.widget_gui.get_visible_range()

            self.widget_gui.freeze_child_notify()
            self.widget_gui.set_model(None)
            try:
                self._display_up_to(self.nb_displayed +
                                    self.NB_EL_DISPLAYED_ADDITIONNAL)
            finally:
                self.widget_gui.freeze_child_notify()
                self.widget_gui.set_model(self.model)

            if (selected > 0):
                path = Gtk.TreePath(selected)
                self.widget_gui.select_path(path)
                self.widget_gui.set_cursor(path, None, False)

            GLib.idle_add(self.widget_gui.scroll_to_path, last_visible,
                          False, 0.0, 0.0)
        finally:
            for action in self.actions:
                action.enabled = True

    def _display_up_to(self, nb_elements):
        l_model = len(self.model)
        if l_model > 0:
            doc = self.model[-1][2]
            if doc is None or doc == 0:
                line_iter = self.model.get_iter(l_model-1)
                self.model.remove(line_iter)

        newly_displayed = []
        for line_idx in range(self.nb_displayed, nb_elements):
            if (self.nb_displayed >= nb_elements
                    or line_idx >= len(self.model_content)):
                break
            newly_displayed.append((line_idx, self.model_content[line_idx][2]))
            self.model.append(self.model_content[line_idx])
            self.nb_displayed += 1

        self.emit('lines-shown', newly_displayed)

        if nb_elements < len(self.model_content):
            padding = [None] * (self.model_nb_columns - 2)
            model_line = [_("Loading ..."), self.default_thumbnail]
            model_line += padding
            self.model.append(model_line)

        logger.info("List '%s' : %d elements displayed (%d additionnal)"
                    % (self.name, self.nb_displayed, len(newly_displayed)))

    def __on_scrollbar_moved(self):
        if self.nb_displayed >= len(self.model_content):
            return

        lower = self._vadjustment.get_lower()
        upper = self._vadjustment.get_upper()
        val = self._vadjustment.get_value()
        proportion = (val - lower) / (upper - lower)

        if proportion > self.NB_EL_DISPLAY_EXTRA_WHEN_LOWER_THAN:
            self.scheduler.cancel_all(self.job_factory)
            job = self.job_factory.make()
            self.scheduler.schedule(job)

    def set_model_value(self, line_idx, column_idx, value):
        self.model_content[line_idx][column_idx] = value
        if line_idx < self.nb_displayed:
            line_iter = self.model.get_iter(line_idx)
            self.model.set_value(line_iter, column_idx, value)

    def set_model_line(self, line_idx, model_line):
        self.model_content[line_idx] = model_line
        if line_idx < self.nb_displayed:
            self.model[line_idx] = model_line

    def pop(self, idx):
        content = self.model_content.pop(idx)
        itr = self.model.get_iter(idx)
        self.model.remove(itr)
        return content

    def insert(self, idx, line):
        self.model_content.insert(idx, line)
        self.model.insert(idx, line)

    def select_idx(self, idx=-1):
        if idx >= 0:
            # we are going to select the current page in the list
            # except we don't want to be called again because of it
            for action in self.actions:
                action.enabled = False
            try:
                self.widget_gui.unselect_all()

                path = Gtk.TreePath(idx)
                self.widget_gui.select_path(path)
                self.widget_gui.set_cursor(path, None, False)
            finally:
                for action in self.actions:
                    action.enabled = True

            # HACK(Jflesch): The Gtk documentation says that scroll_to_path()
            # should do nothing if the target cell is already visible (which
            # is the desired behavior here). Except we just emptied the
            # document list model and remade it from scratch. For some reason,
            # it seems that Gtk will then always consider that the cell is
            # not visible and move the scrollbar.
            # --> we use idle_add to move the scrollbar only once everything
            # has been displayed
            GLib.idle_add(self.widget_gui.scroll_to_path,
                          path, False, 0.0, 0.0)
        else:
            self.unselect()

    def unselect(self):
        self.widget_gui.unselect_all()
        path = Gtk.TreePath(0)
        GLib.idle_add(self.widget_gui.scroll_to_path,
                      path, False, 0.0, 0.0)

    def __getitem__(self, item):
        return {
            'gui': self.widget_gui,
            'model': self.model_content,
            'scrollbars': self.widget_scrollbars
        }[item]


GObject.type_register(ProgressiveList)
