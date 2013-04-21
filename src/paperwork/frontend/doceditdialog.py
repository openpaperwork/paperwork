import datetime

import gettext
from gi.repository import Gtk

from paperwork.util import load_uifile

_ = gettext.gettext

class DocEditDialog(object):
    def __init__(self, main_window, config, doc):
        self.__main_win = main_window
        self.__config = config
        self.doc = doc

        widget_tree = load_uifile("doceditdialog.glade")
        self.date = {
            'year' : {
                'view' : widget_tree.get_object("spinbuttonYear"),
                'model' : widget_tree.get_object("adjustmentYear"),
            },
            'month' : {
                'view' : widget_tree.get_object("spinbuttonMonth"),
                'model' : widget_tree.get_object("adjustmentMonth"),
            },
            'day' : {
                'view' : widget_tree.get_object("spinbuttonDay"),
                'model' : widget_tree.get_object("adjustmentDay"),
            },
        }

        # TODO(Jflesch): Reorder the widget according the to the locale

        self.refresh_date()

        self.dialog = widget_tree.get_object("dialogDocEdit")
        self.dialog.set_transient_for(self.__main_win.window)

        must_run = True
        try:
            while must_run:
                ret = self.dialog.run()
                if ret != 0:
                    must_run = False
                else:
                    try:
                        self.set_date()
                    except ValueError:
                        self.__show_error(_("Invalid date"))
        finally:
            self.dialog.destroy()

    def __show_error(self, msg):
        dialog = \
                Gtk.MessageDialog(parent=self.dialog,
                                  flags=(Gtk.DialogFlags.MODAL
                                         |Gtk.DialogFlags.DESTROY_WITH_PARENT),
                                  type=Gtk.MessageType.ERROR,
                                  buttons=Gtk.ButtonsType.OK,
                                  message_format=msg)
        dialog.run()
        dialog.destroy()

    def refresh_date(self):
        date = self.doc.date
        self.date['year']['model'].set_value(date[0])
        self.date['month']['model'].set_value(date[1])
        self.date['day']['model'].set_value(date[2])

    def __check_date(self, date):
        datetime.datetime(year=date[0],
                          month=date[1],
                          day=date[2])

    def set_date(self):
        date = (int(self.date['year']['model'].get_value()),
                int(self.date['month']['model'].get_value()),
                int(self.date['day']['model'].get_value()))
        self.__check_date(date)

        docsearch = self.__main_win.docsearch
        doc_index_updater = docsearch.get_index_updater(optimize=False)
        doc_index_updater.del_doc(self.doc.docid)

        self.doc.date = date

        doc_index_updater.add_doc(self.doc)
        doc_index_updater.commit()

        self.__main_win.refresh_doc_list()
