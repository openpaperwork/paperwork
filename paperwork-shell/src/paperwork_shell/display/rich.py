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
import rich.text

from openpaperwork_core.interfaces.print import Print
from openpaperwork_core.interfaces.shell import Shell
import openpaperwork_core


class Plugin(
    openpaperwork_core.PluginBase,
    Print,
    Shell,
):
    PRIORITY = 1000

    def __init__(self, core):
        super().__init__(core)
        self.output = []
        self.console = None

    def cmd_set_console(self, console):
        self.console = console

    @openpaperwork_core.noop
    def cmd_complete_argparse(self, parser):
        pass

    @openpaperwork_core.noop
    def cmd_run(self, console, args):
        pass

    def print(self, txt):
        self.output.append(txt)
        return True

    def print_isatty(self):
        if self.console is not None:
            return True
        return None

    def print_flush(self):
        if self.console is None:
            return None
        for line in self.output:
            richer = rich.text.Text.from_ansi(line) if isinstance(line, str) else line
            self.console.console.print(richer)
        self.output = []
        return True
