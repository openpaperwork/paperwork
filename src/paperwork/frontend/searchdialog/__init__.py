import os

from paperwork.frontend.util import load_uifile


class SearchDialog(object):
    def __init__(self, main_window):
        widget_tree = load_uifile(
            os.path.join("searchdialog", "searchdialog.glade"))

        self.dialog = widget_tree.get_object("searchDialog")
        self.dialog.set_transient_for(main_window.window)

    def run(self):
        response = self.dialog.run()
        self.dialog.destroy()
        return response

    def get_search_string(self):
        # TODO
        return u""
