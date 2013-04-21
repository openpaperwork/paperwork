import datetime

import gettext
import locale
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
            'box' : widget_tree.get_object("boxDate")
        }

        self.__change_widget_order_according_to_locale()

        self.refresh_date()

        self.dialog = widget_tree.get_object("dialogDocEdit")
        self.dialog.set_transient_for(self.__main_win.window)

        try:
            while True:
                ret = self.dialog.run()
                if ret != 0:
                    break
                else:
                    try:
                        self.set_date()
                    except ValueError:
                        self.__show_error(_("Invalid date"))
                        continue
                    break
        finally:
            self.dialog.destroy()

    def __change_widget_order_according_to_locale(self):
        widgets = {
            "year" : self.date['year']['view'],
            "month" : self.date['month']['view'],
            "day" : self.date['day']['view']
        }
        char_to_widget = {
            'B' : "month",
            'd' : "day",
            'm' : "month",
            'y' : "year",
            'Y' : "year",
        }
        new_order = []

        date_format = locale.nl_langinfo(locale.D_FMT)
        split = date_format.split("%")
        for element in split:
            if len(element) <= 0:
                continue
            char = element[0]
            if not char in char_to_widget:
                continue
            widget_name = char_to_widget[char]
            if not widget_name in widgets:
                # already placed
                continue
            widget = widgets.pop(widget_name)
            new_order.append(widget)
        if len(widgets) > 0:
            print ("WARNING: Failed to figure out the correct order"
                   " for the date widget")
            print "Will use ISO order"
            return

        for widget in self.date['box'].get_children():
            self.date['box'].remove(widget)
        for widget in new_order:
            self.date['box'].add(widget)
        self.date['box'].add(Gtk.Label(""))

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
        print "Doc date: %s" % str(date)
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
