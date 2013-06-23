import datetime

import gettext
import logging
import locale
from gi.repository import Gtk

from paperwork.util import load_uifile

_ = gettext.gettext
logger = logging.getLogger(__name__)


class DocEditDialog(object):
    def __init__(self, main_window, config, doc):
        self.__main_win = main_window
        self.__config = config
        self.doc = doc

        widget_tree = load_uifile("doceditdialog.glade")
        self.date = {
            'year': {
                'view': widget_tree.get_object("spinbuttonYear"),
                'model': widget_tree.get_object("adjustmentYear"),
            },
            'month': {
                'view': widget_tree.get_object("spinbuttonMonth"),
                'model': widget_tree.get_object("adjustmentMonth"),
            },
            'day': {
                'view': widget_tree.get_object("spinbuttonDay"),
                'model': widget_tree.get_object("adjustmentDay"),
            },
            'box': widget_tree.get_object("boxDate")
        }
        self.text = {
            'view': widget_tree.get_object("textviewText"),
            'model': widget_tree.get_object("textbufferText"),
        }

        self.__change_widget_order_according_to_locale()

        self.refresh_date()
        self.refresh_text()

        self.dialog = widget_tree.get_object("dialogDocEdit")
        self.dialog.set_transient_for(self.__main_win.window)

        try:
            while True:
                ret = self.dialog.run()
                if ret != 0:
                    logger.info("Doc edit: Cancelling changes")
                    break
                else:
                    logger.info("Doc edit: Applying changes")
                    if self.apply_changes():
                        break
        finally:
            self.dialog.destroy()

    def __change_widget_order_according_to_locale(self):
        widgets = {
            "year": self.date['year']['view'],
            "month": self.date['month']['view'],
            "day": self.date['day']['view']
        }
        char_to_widget = {
            'B': "month",
            'd': "day",
            'm': "month",
            'y': "year",
            'Y': "year",
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
            logger.warn("WARNING: Failed to figure out the correct order"
                   " for the date widget")
            logger.info("Will use ISO order")
            return

        for widget in self.date['box'].get_children():
            self.date['box'].remove(widget)
        for widget in new_order:
            self.date['box'].add(widget)
        self.date['box'].add(Gtk.Label(""))

    def refresh_date(self):
        date = self.doc.date
        logger.info("Doc date: %s" % str(date))
        self.date['year']['model'].set_value(date.year)
        self.date['month']['model'].set_value(date.month)
        self.date['day']['model'].set_value(date.day)

    def refresh_text(self):
        self.text['model'].set_text(self.doc.extra_text)

    def set_date(self):

        date = datetime.datetime(
            int(self.date['year']['model'].get_value()),
            int(self.date['month']['model'].get_value()),
            int(self.date['day']['model'].get_value()))
        if date == self.doc.date:
            logger.info("Date unchanged")
            return False

        logger.info("Date changed")
        self.doc.date = date

        self.__main_win.refresh_doc_list()
        return True

    def set_text(self):
        start = self.text['model'].get_iter_at_offset(0)
        end = self.text['model'].get_iter_at_offset(-1)
        txt = unicode(self.text['model'].get_text(start, end, False),
                      encoding='utf-8')
        if self.doc.extra_text == txt:
            logger.info("Extra text unchanged")
            return False
        logger.info("Extra text changed")
        self.doc.extra_text = txt
        return True

    def __show_error(self, msg):
        flags = (Gtk.DialogFlags.MODAL
                 | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(parent=self.dialog,
                                   flags=flags,
                                   type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK,
                                   message_format=msg)
        dialog.run()
        dialog.destroy()

    def apply_changes(self):
        docsearch = self.__main_win.docsearch
        doc_index_updater = docsearch.get_index_updater(optimize=False)
        doc_index_updater.del_doc(self.doc.docid)

        changed = False

        try:
            changed = self.set_date() or changed
        except ValueError:
            self.__show_error(_("Invalid date"))
            return False
        changed = self.set_text() or changed

        if changed:
            doc_index_updater.add_doc(self.doc)
            doc_index_updater.commit()
            self.__main_win.refresh_doc_list()
        else:
            doc_index_updater.cancel()
        return True
