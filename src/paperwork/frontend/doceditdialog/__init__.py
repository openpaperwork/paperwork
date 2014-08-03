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

import datetime
import os

import gettext
import logging
import locale
from gi.repository import Gtk
from gi.repository import GLib

from paperwork.frontend.util import load_uifile


_ = gettext.gettext
logger = logging.getLogger(__name__)


class OnSpinButtonChange(object):

    def __init__(self, spin_button, fmt='%02d'):
        self.fmt = fmt
        spin_button.connect("output", self.__on_output)

    def __on_output(self, spin_button):
        adj = spin_button.get_adjustment()
        val = adj.get_value()
        spin_button.set_text(self.fmt % val)
        return True


class OnYearSpinButtonChange(OnSpinButtonChange):

    def __init__(self, spin_button):
        OnSpinButtonChange.__init__(self, spin_button, fmt='%04d')
        self.spin_button = spin_button

        # XXX(Jflesch): This is the wrong signal
        # we should use 'input', but unfortunately, it seems we can't
        # use it in Python ...
        # Lucky for us, we should never loop by doing so.
        spin_button.connect('value-changed', lambda _:
                            GLib.idle_add(self.__on_value_changed))

    def __on_value_changed(self):
        value = self.spin_button.get_value()
        current_y = datetime.datetime.now().year
        min_y = current_y - 50
        add_y = int(min_y / 100) * 100
        if value < 100:
            value += add_y
            if value <= min_y:
                value += 100
            self.spin_button.set_value(value)


class DocEditDialog(object):

    def __init__(self, main_window, config, doc):
        self.__main_win = main_window
        self.__config = config
        self.doc = doc

        widget_tree = load_uifile(
            os.path.join("doceditdialog", "doceditdialog.glade"))
        self.date = {
            'year': {
                'view': widget_tree.get_object("spinbuttonYear"),
                'model': widget_tree.get_object("adjustmentYear"),
                'fmt': OnYearSpinButtonChange,
            },
            'month': {
                'view': widget_tree.get_object("spinbuttonMonth"),
                'model': widget_tree.get_object("adjustmentMonth"),
                'fmt': OnSpinButtonChange,
            },
            'day': {
                'view': widget_tree.get_object("spinbuttonDay"),
                'model': widget_tree.get_object("adjustmentDay"),
                'fmt': OnSpinButtonChange,
            },
            'box': widget_tree.get_object("boxDate")
        }
        self.text = {
            'view': widget_tree.get_object("textviewText"),
            'model': widget_tree.get_object("textbufferText"),
        }

        self.dialog = widget_tree.get_object("dialogDocEdit")

        for widgets in self.date.values():
            if 'fmt' not in widgets:
                continue
            widgets['fmt'](widgets['view'])
            widgets['view'].connect(
                "activate",
                lambda _: self.dialog.response(Gtk.ResponseType.OK)
            )

        self.__change_widget_order_according_to_locale()

        self.refresh_date()
        self.refresh_text()

        self.dialog.set_transient_for(self.__main_win.window)

        try:
            while True:
                ret = self.dialog.run()
                if int(ret) != int(Gtk.ResponseType.OK):
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
            if char not in char_to_widget:
                continue
            widget_name = char_to_widget[char]
            if widget_name not in widgets:
                # already placed
                continue
            widget = widgets.pop(widget_name)
            new_order.append(widget)
        if len(widgets) > 0:
            logger.warning("WARNING: Failed to figure out the correct order"
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
                                   message_type=Gtk.MessageType.ERROR,
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
