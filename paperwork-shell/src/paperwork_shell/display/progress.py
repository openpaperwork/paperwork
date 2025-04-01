#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2019  Jerome Flesch
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

import openpaperwork_core

import rich.progress


LOGGER = logging.getLogger(__name__)

TIME_BETWEEN_PROGRESS = 0.3


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return [
            'progress_listener',
        ]

    def __init__(self, core):
        super().__init__(core)
        self.console = None
        self.progress = None
        self.tasks = {}

    def cmd_set_console(self, console):
        if console is None:
            return
        self.console = console

    def on_progress(self, upd_type, progress, description=None):
        if self.progress is None:
            self.progress = rich.progress.Progress(
                console=self.console.console
            )
            self.progress.start()
            return
        if upd_type not in self.tasks:
            if progress >= 1.0:
                return
            assert description is not None
            self.tasks[upd_type] = self.progress.add_task(
                description=description, total=1.0
            )
        if progress >= 1.0:
            task_id = self.tasks.pop(upd_type)
            self.progress.remove_task(task_id)
        else:
            task_id = self.tasks[upd_type]
            self.progress.update(task_id, completed=progress)

    def on_quit(self):
        if self.progress is None:
            return
        self.progress.stop()
