#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2025 Jerome Flesch
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
import sys

from openpaperwork_core.interfaces.print import Print
import openpaperwork_core


class Plugin(
    openpaperwork_core.PluginBase,
    Print,
):
    def __init__(self, core):
        super().__init__(core)
        self.output = []

    def print(self, txt):
        self.output.append(txt)

    @openpaperwork_core.noop
    def print_isatty(self):
        pass

    def print_flush(self):
        output = "\n".join(self.output)
        sys.stdout.write(output)
        self.output = []
