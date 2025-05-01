import datetime
import logging
import re

from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.i18n import I18n
from openpaperwork_core.interfaces.chkdeps import Chkdeps
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
from openpaperwork_gtk.interfaces.screenshot import Screenshot
from openpaperwork_gtk.interfaces.screenshot import ScreenshotProvider
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.doc_labels import DocLabelListener, DocLabels

from paperwork_gtk import _
from paperwork_gtk.interfaces.advanced_search import AdvancedSearchDialog
from paperwork_gtk.interfaces.search_field import SearchField

try:
    from gi.repository import GLib
    from gi.repository import GObject
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


def strip_quotes(txt):
    if txt[0] == u'"' and txt[-1] == u'"':
        return txt[1:-1]
    if txt[0] == u'\'' and txt[-1] == u'\'':
        return txt[1:-1]
    return txt


class SearchElement:
    def __init__(self, dialog, widget):
        self.dialog = dialog
        self.widget = widget
        widget.set_hexpand(True)
        widget.show_all()

    def get_widget(self):
        return self.widget

    def get_search_string(self):
        assert False

    @staticmethod
    def get_from_search(dialog, text):
        assert False

    @staticmethod
    def get_name():
        assert False

    def on_model_updated(self):
        pass


class SearchElementText(SearchElement):
    """This is the keyword search term text field"""
    def __init__(self, dialog):
        super(SearchElementText, self).__init__(dialog, Gtk.Entry())

    def get_search_string(self):
        txt = self.widget.get_text()
        txt = txt.replace('"', '\\"')
        return '"%s"' % txt

    @staticmethod
    def get_from_search(dialog, text):
        text = strip_quotes(text)
        element = SearchElementText(dialog)
        element.widget.set_text(text)
        return element

    @staticmethod
    def get_name():
        return _("Keyword(s)")

    def __str__(self):
        return ("Text: [%s]" % self.widget.get_text())


class SearchElementLabel(SearchElement):
    def __init__(self, dialog):
        super().__init__(dialog, Gtk.ComboBoxText())
        self.on_model_updated()
        self.widget.set_active(0)

    def on_model_updated(self):
        labels = set()
        self.dialog.core.call_all(DocLabels.labels_get_all, labels)
        labels = [label[0] for label in labels]
        labels = self.dialog.core.call_success(I18n.i18n_sort, labels)

        store = Gtk.ListStore.new([GObject.TYPE_STRING])
        if len(labels) <= 0:
            # happens temporarily when Paperwork starts
            store.append([_("No labels")])
            self.widget.set_sensitive(False)
        else:
            for label in labels:
                store.append([label])
            self.widget.set_sensitive(True)
        self.widget.set_model(store)

    def get_search_string(self):
        active_idx = self.get_widget().get_active()
        if active_idx < 0:
            return ""
        model = self.get_widget().get_model()
        txt = model[active_idx][0]
        txt = txt.replace('"', '\\"')
        return 'label:"%s"' % txt

    @staticmethod
    def get_from_search(dialog, text):
        if not text.startswith(u"label:"):
            return None

        text = text[len(u"label:"):]
        text = strip_quotes(text)

        element = SearchElementLabel(dialog)

        active_idx = -1
        idx = 0
        for line in element.get_widget().get_model():
            value = line[0]
            if value == text:
                active_idx = idx
            idx += 1
        element.get_widget().set_active(active_idx)

        return element

    @staticmethod
    def get_name():
        return _("Label")

    def __str__(self):
        return ("Label: [%d]" % self.get_widget().get_active())


class SearchElementDate(SearchElement):
    """Search entry using a time span"""
    def __init__(self, dialog):
        box = Gtk.Box()
        box.set_spacing(10)

        label = Gtk.Label.new(_("From:"))
        box.add(label)

        self.start_date = self._make_date_widget()
        box.add(self.start_date)

        label = Gtk.Label.new(_("to:"))
        box.add(label)

        self.end_date = self._make_date_widget()
        box.add(self.end_date)
        super(SearchElementDate, self).__init__(dialog, box)

        self.calendar_popover = dialog.widget_tree.get_object(
            "calendar_popover"
        )
        self.calendar = dialog.widget_tree.get_object("calendar_calendar")

        self.current_entry = None
        self.calendar.connect(
            "day-selected-double-click",
            lambda _: GLib.idle_add(self._close_calendar)
        )

    def _make_date_widget(self):
        entry = Gtk.Entry()
        entry.set_text("")
        entry.set_property("secondary_icon_sensitive", True)
        entry.set_property("secondary_icon_name", "x-office-calendar-symbolic")
        entry.connect(
            "icon-release",
            lambda entry, icon, event:
            GLib.idle_add(self._open_calendar, entry)
        )
        return entry

    @staticmethod
    def _parse_date(txt):
        txt = txt.strip()
        if txt == u"":
            dt = datetime.datetime.today()
        else:
            try:
                dt = datetime.datetime.strptime(txt, "%Y%m%d")
            except ValueError:
                LOGGER.warning(
                    "Failed to parse [%s]. Will use today date", txt
                )
                dt = datetime.datetime.today()
        return (dt.year, dt.month, dt.day)

    @staticmethod
    def _format_date(date):
        return "%04d%02d%02d" % (date[0], date[1], date[2])

    def _open_calendar(self, entry):
        self.calendar_popover.set_relative_to(entry)
        date = self._parse_date(entry.get_text())
        self.calendar.select_month(date[1] - 1, date[0])
        self.calendar.select_day(date[2])
        self.calendar_popover.show_all()
        self.current_entry = entry

    def _close_calendar(self):
        date = self.calendar.get_date()
        date = datetime.datetime(year=date[0], month=date[1] + 1, day=date[2])
        date = self._format_date((date.year, date.month, date.day))
        self.current_entry.set_text(date)
        self.calendar_popover.set_visible(False)

    def get_search_string(self):
        start_date = self._parse_date(self.start_date.get_text())
        end_date = self._parse_date(self.end_date.get_text())
        if end_date < start_date:
            tmp_date = start_date
            start_date = end_date
            end_date = tmp_date
        if start_date == end_date:
            return (
                "date:%04d%02d%02d"
                % (start_date[0], start_date[1], start_date[2])
            )
        return (
            'date:[%04d%02d%02d to %04d%02d%02d]' % (
                start_date[0], start_date[1], start_date[2],
                end_date[0], end_date[1], end_date[2]
            )
        )

    @staticmethod
    def get_from_search(dialog, txt):
        if not txt.startswith(u"date:"):
            return None

        txt = txt[len(u"date:"):]
        txt = strip_quotes(txt)

        if txt[0] == "[" and txt[-1] == "]":
            txt = txt[1:-1]
        if " to " in txt:
            txt = txt.split(" to ", 1)
        else:
            txt = [txt, txt]

        dates = [
            SearchElementDate._parse_date(date)
            for date in txt
        ]

        se = SearchElementDate(dialog)
        se.start_date.set_text(se._format_date(dates[0]))
        se.end_date.set_text(se._format_date(dates[1]))
        return se

    @staticmethod
    def get_name():
        return _("Date")

    def __str__(self):
        return (
            "Date: [%s] - [%s]"
            % (self.start_date.get_text(), self.end_date.get_text())
        )


class SearchLine(object):
    SELECT_ORDER = [
        SearchElementText,
        SearchElementLabel,
        SearchElementDate,
    ]
    TXT_EVAL_ORDER = [
        SearchElementDate,
        SearchElementLabel,
        SearchElementText,
    ]

    def __init__(self, dialog, has_operator, has_remove_button):
        LOGGER.info("Search line instantiated")

        self.dialog = dialog
        self.line = []

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
            self.line.append(self.combobox_operator)
        else:
            self.combobox_operator = None
            placeholder = Gtk.Label.new("")
            placeholder.set_size_request(75, -1)
            self.line.append(placeholder)

        model = Gtk.ListStore.new([
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
        ])
        model.append(["", ""])
        model.append([_("not"), "NOT"])
        self.combobox_not = Gtk.ComboBoxText.new()
        self.combobox_not.set_model(model)
        self.combobox_not.set_size_request(75, -1)
        self.combobox_not.set_active(0)
        self.line.append(self.combobox_not)

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

        self.placeholder = Gtk.Label.new("")
        self.placeholder.set_hexpand(True)

        self.element = None
        self.remove_button = Gtk.Button.new_with_label(_("Remove"))

        self.line.append(self.combobox_type)
        self.line.append(self.placeholder)
        if has_remove_button:
            self.line.append(self.remove_button)
        else:
            self.line.append(Gtk.Label.new(""))

        self.combobox_type.set_active(0)

        self.change_element()

    def connect_signals(self):
        self.combobox_type.connect(
            "changed", lambda w: GLib.idle_add(self.change_element)
        )
        self.remove_button.connect(
            "clicked",
            lambda x: GLib.idle_add(
                self.dialog._remove_element,
                self
            )
        )

    @staticmethod
    def _select_value(combobox, value):
        if not combobox:
            return
        active_idx = 0
        model = combobox.get_model()
        for line in model:
            if line[1] == value:
                LOGGER.info("Element %d selected", active_idx)
                combobox.set_active(active_idx)
                return
            active_idx += 1
        assert False

    def select_operator(self, operator):
        self._select_value(self.combobox_operator, operator.upper())

    def select_not(self, not_value):
        self._select_value(self.combobox_not, not_value)

    def select_element_type(self, et):
        self._select_value(self.combobox_type, et)

    def change_element(self):
        LOGGER.info("Element changed")
        active_idx = self.combobox_type.get_active()
        if (active_idx < 0):
            return
        element_class = self.combobox_type.get_model()[active_idx][1]
        element = element_class(self.dialog)
        self.set_element(element)

    def set_element(self, element):
        LOGGER.info("Set element: %s", str(element))
        if self.placeholder:
            self.line.remove(self.placeholder)
            self.placeholder = None
        if self.element:
            self.line.remove(self.element.get_widget())
            self.element = None
        self.line.insert(3, element.get_widget())
        self.element = element
        self.dialog._rebuild()

    def get_widgets(self):
        return self.line

    @staticmethod
    def _get_combobox_value(combobox):
        active_idx = combobox.get_active()
        if (active_idx < 0):
            return ""
        value = combobox.get_model()[active_idx][1]
        return value

    def get_operator(self):
        if not self.combobox_operator:
            return u""
        return self._get_combobox_value(self.combobox_operator)

    def get_not(self):
        return self._get_combobox_value(self.combobox_not)

    def get_search_string(self):
        if self.element is None:
            return ""
        return self.element.get_search_string()

    @staticmethod
    def get_from_search(dialog, next_operator, not_value, search_txt):
        for se_class in SearchLine.TXT_EVAL_ORDER:
            se = se_class.get_from_search(dialog, search_txt)
            if not se:
                continue
            sl = SearchLine(
                dialog,
                next_operator is not None,
                next_operator is not None
            )
            if next_operator:
                sl.select_operator(next_operator)
            sl.select_element_type(se_class)
            sl.select_not(not_value)
            sl.set_element(se)
            sl.connect_signals()
            LOGGER.info(
                "Loaded from search: %s --> %s", search_txt, str(se)
            )
            return sl
        assert False

    def on_model_updated(self):
        if self.element:
            self.element.on_model_updated()


class Plugin(
    openpaperwork_core.PluginBase,
    AdvancedSearchDialog,
    Chkdeps,
    DocLabelListener,
    GtkWindowListener,
    ScreenshotProvider,
):
    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocLabels,
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                "interface": Fs,
                "defaults": ["openpaperwork.fs.gio"],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': I18n,
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                'interface': Screenshot,
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
            {
                "interface": SearchField,
                "defaults": ["paperwork_gtk.mainwindow.search.field"],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.widget_tree = None
        self.windows = []
        self.search_element_box = None
        self.search_elements = []
        self.dialog = None

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def gtk_open_advanced_search_dialog(self):
        if self.dialog is not None:
            LOGGER.warning("Advanced search dialog already opened")
            return

        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.search", "advanced.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.dialog = self.widget_tree.get_object("search_dialog")
        self.dialog.set_transient_for(self.windows[-1])

        keywords = self.core.call_success(SearchField.search_get)
        keywords = keywords.strip()
        keywords = re.findall(
            r'(?:\[.*\]|(?:[^\s"]|"(?:\\.|[^"])*"))+', keywords
        )

        self.search_element_box = self.widget_tree.get_object(
            "box_search_elements"
        )
        self.search_elements = []

        add_button = self.widget_tree.get_object("button_add")
        add_button.connect(
            "clicked", lambda w: GLib.idle_add(self._add_element)
        )

        if keywords == []:
            LOGGER.info("Starting from an empty search")
            self._add_element()
        else:
            LOGGER.info("Current search: %s", keywords)

            next_operator = None
            not_value = u""
            for keyword in keywords:
                if keyword.upper() == u"AND":
                    next_operator = u"AND"
                    continue
                elif keyword.upper() == u"OR":
                    next_operator = u"OR"
                    continue
                elif keyword.upper() == u"NOT":
                    not_value = u"NOT"
                    continue

                LOGGER.info("Instantiating line for [%s]", keyword)
                sl = SearchLine.get_from_search(
                    self, next_operator, not_value, keyword
                )
                self._add_element(sl)

                next_operator = u"AND"
                not_value = u""

        self.dialog.connect("response", self._on_response)
        self.dialog.show_all()

    def _on_response(self, dialog, response_id):
        if (response_id == Gtk.ResponseType.ACCEPT or
                response_id == Gtk.ResponseType.OK or
                response_id == Gtk.ResponseType.YES or
                response_id == Gtk.ResponseType.APPLY):
            search = self._get_search_string()
            self.core.call_all(SearchField.search_set, search)
        self.gtk_close_advanced_search_dialog()

    def gtk_close_advanced_search_dialog(self):
        self.dialog.destroy()
        self.widget_tree = None
        self.dialog = None

    def _add_element(self, sl=None):
        if sl is None:
            sl = SearchLine(
                self,
                len(self.search_elements) > 0,
                len(self.search_elements) > 0
            )
            sl.connect_signals()
        self.search_elements.append(sl)
        self._rebuild()

    def _rebuild(self):
        # purge
        for child in self.search_element_box.get_children():
            self.search_element_box.remove(child)

        # rebuild
        for (line, sl) in enumerate(self.search_elements):
            for (pos, widget) in enumerate(sl.get_widgets()):
                self.search_element_box.attach(
                    widget,
                    pos, line,
                    1, 1
                )
        self.search_element_box.show_all()

    def _remove_element(self, sl):
        self.search_elements.remove(sl)
        self._rebuild()

    def _get_search_string(self):
        """concat all our search terms into a single string"""
        out = ""
        for element in self.search_elements:
            # Add AND/OR
            oper = element.get_operator()
            out += " %s " % oper
            not_value = element.get_not()
            if not_value:
                out += "%s " % not_value
            out += element.get_search_string()
        out = out.strip()
        LOGGER.info("Search: [%s]", out)
        return out

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.dialog is None:
            return
        self.core.call_success(
            Screenshot.screenshot_snap_widget,
            self.dialog,
            self.core.call_success(
                Fs.fs_join, out_dir, "advanced_search.png"
            ),
        )

    @openpaperwork_core.noop
    def on_label_loading_start(self):
        pass

    def on_label_loading_end(self):
        for element in self.search_elements:
            element.on_model_updated()
