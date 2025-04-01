"""
Takes care of the few things that must be done if we are running in an
executable created with cx_freeze.

It must be loaded as early as possible.
"""
import multiprocessing
import os
import sys

from . import PluginBase


class Plugin(PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['frozen']

    def __init__(self, core):
        super().__init__(core)
        if not getattr(sys, 'frozen', False):
            return
        self._set_meipass()
        multiprocessing.freeze_support()

    def _set_meipass(self):
        # If sys.frozen, then Pyocr (and possibly others) needs MEIPASS to be
        # set *before* importing it.
        if getattr(sys, '_MEIPASS', False):
            # Pyinstaller case
            return
        # Cx_Freeze case
        if "python" not in sys.executable or '__file__' not in globals():
            sys._MEIPASS = os.path.dirname(os.path.realpath(sys.executable))
        else:
            sys._MEIPASS = os.path.realpath(os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "..", ".."
            ))
