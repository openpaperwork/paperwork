import os

import logging
import gettext
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from paperwork.frontend.util import load_uifile


_ = gettext.gettext
logger = logging.getLogger(__name__)


class SearchElement(object):
    def __init__(self, dialog, widget):
        self.dialog = dialog
        self.widget = widget
        widget.set_hexpand(True)
        widget.show_all()

    def get_widget(self):
        return self.widget

    def get_search_string(self):
        assert()

    @staticmethod
    def get_from_search(dialog, text):
        assert()

    @staticmethod
    def get_name():
        assert()


class SearchElementText(SearchElement):
    def __init__(self, dialog):
        super(SearchElementText, self).__init__(dialog, Gtk.Entry())

    def get_search_string(self):
        txt = self.widget.get_text().decode("utf-8")
        txt = txt.replace('"', '\\"')
        if " " in txt:
            txt = '"' + txt + '"'
        return txt

    @staticmethod
    def get_from_search(dialog, text):
        element = SearchElementText(dialog)
        element.widget.set_text(text)
        return element

    @staticmethod
    def get_name():
        return _("Keyword(s)")


class SearchElementLabel(SearchElement):
    def __init__(self, dialog):
        super(SearchElementLabel, self).__init__(dialog, Gtk.ComboBoxText())
        labels = self.dialog._labels
        store = Gtk.ListStore.new([GObject.TYPE_STRING])
        for label in labels:
            store.append([label.name])
        self.widget.set_model(store)
        self.widget.set_active(0)

    def get_search_string(self):
        active_idx = self.get_widget().get_active()
        if active_idx < 0:
            return u""
        model = self.get_widget().get_model()
        txt = model[active_idx][0].decode("utf-8")
        txt = txt.replace('"', '\\"')
        return u"label:\"" + txt + "\""

    @staticmethod
    def get_from_search(dialog, text):
        if not text.startswith("label:"):
            return None

        text = text[len("label:"):]
        text = unicode(text)

        element = SearchElementLabel(dialog)

        active_idx = -1
        idx = 0
        for line in element.get_widget().get_model():
            value = line[0].decode("utf-8")
            if value == text:
                active_idx = idx
            idx += 1
        element.get_widget().set_active(active_idx)

        return element

    @staticmethod
    def get_name():
        return _("Label")


class SearchLine(object):
    SELECT_ORDER = [
        SearchElementText,
        SearchElementLabel,
    ]
    TXT_EVAL_ORDER = [
        SearchElementLabel,
        SearchElementText,
    ]

    def __init__(self, dialog, has_operator):
        self.dialog = dialog
        self.line = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 10)

        if has_operator:
            model = Gtk.ListStore.new([
                GObject.TYPE_STRING,
                GObject.TYPE_STRING,
            ])
            model.append([_("and"), "AND"])
            model.append([_("or"), "OR"])
            self.combobox_operator = Gtk.ComboBoxText.new()
            self.combobox_operator.set_model(model)
            self.combobox_operator.set_size_request(75, -1)
            self.combobox_operator.set_active(0)
            self.line.add(self.combobox_operator)
        else:
            self.combobox_operator = None
            placeholder = Gtk.Label.new("")
            placeholder.set_size_request(75, -1)
            self.line.add(placeholder)

        model = Gtk.ListStore.new([
            GObject.TYPE_STRING,
            GObject.TYPE_PYOBJECT,
        ])
        for element in self.SELECT_ORDER:
            model.append([
                element.get_name(),
                element
            ])

        self.combobox_type = Gtk.ComboBoxText.new()
        self.combobox_type.set_model(model)
        self.combobox_type.connect(
            "changed", lambda w: GLib.idle_add(self.change_element)
        )

        self.placeholder = Gtk.Label.new("")
        self.placeholder.set_hexpand(True)

        self.element = None
        self.remove_button = Gtk.Button.new_with_label(_("Remove"))
        self.remove_button.connect(
            "clicked",
            lambda x: GLib.idle_add(
                self.dialog.remove_element,
                self
            )
        )

        self.line.add(self.combobox_type)
        self.line.add(self.placeholder)
        self.line.add(self.remove_button)

        self.combobox_type.set_active(0)

    def change_element(self):
        active_idx = self.combobox_type.get_active()
        if (active_idx < 0):
            return
        element_class = self.combobox_type.get_model()[active_idx][1]
        element = element_class(self.dialog)

        if self.placeholder:
            self.line.remove(self.placeholder)
            self.placeholder = None
        if self.element:
            self.line.remove(self.element.get_widget())
            self.element = None
        self.line.add(element.get_widget())
        self.line.reorder_child(element.get_widget(), 2)
        self.element = element

    def get_widget(self):
        return self.line

    def get_operator(self):
        if not self.combobox_operator:
            return u""
        active_idx = self.combobox_operator.get_active()
        if (active_idx < 0):
            return u""
        operator = self.combobox_operator.get_model()[active_idx][1]
        return operator.decode("utf-8")

    def get_search_string(self):
        if self.element is None:
            return u""
        return self.element.get_search_string()


class SearchDialog(object):
    def __init__(self, main_window):
        widget_tree = load_uifile(
            os.path.join("searchdialog", "searchdialog.glade"))

        self.__main_win = main_window
        self._labels = self.__main_win.docsearch.label_list

        self.dialog = widget_tree.get_object("searchDialog")
        self.dialog.set_transient_for(main_window.window)

        self.__search_string = None

        self.search_element_box = widget_tree.get_object("boxSearchElements")
        self.search_elements = []

        add_button = widget_tree.get_object("buttonAdd")
        add_button.connect("clicked",
                           lambda w: GLib.idle_add(self.add_element))

        self.add_element()
        self.update_search_elements(
            self.__main_win.search_field.get_text().decode("utf-8")
        )

    def run(self):
        response = self.dialog.run()
        self.__search_string = self.__get_search_string()
        self.dialog.destroy()
        return response

    def add_element(self, sl=None):
        if sl is None:
            sl = SearchLine(self, len(self.search_elements) > 0)
        sl.get_widget().show_all()
        self.search_element_box.add(sl.get_widget())
        self.search_elements.append(sl)

    def remove_element(self, sl):
        self.search_element_box.remove(sl.get_widget())
        self.search_elements.remove(sl)

    def update_search_elements(self, search_text):
        # TODO
        pass

    def __get_search_string(self):
        out = u""
        for element in self.search_elements:
            out += element.get_operator() + u" "
            out += element.get_search_string() + u" "
        out = out.strip()
        logger.info("Search: [%s]" % out)
        return out

    def get_search_string(self):
        return self.__search_string
