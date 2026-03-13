import datetime

from openpaperwork_core.interfaces.i18n import I18n
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.widgets import GtkCalendarWidget


class Plugin(
    openpaperwork_core.PluginBase,
    GtkCalendarWidget,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=I18n,
                defaults=['openpaperwork_core.i18n.python'],
            ),
        ]

    def add_popover(self, gtk_entry):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "openpaperwork_gtk.widgets.calendar", "calendar.glade"
        )
        widget_tree.get_object("calendar_popover").set_relative_to(
            gtk_entry
        )
        gtk_entry.connect(
            "icon-release", self._open_calendar, widget_tree
        )
        widget_tree.get_object("calendar_calendar").connect(
            "day-selected-double-click",
            self._update_date, gtk_entry, widget_tree
        )

    def _open_calendar(
            self, gtk_entry, icon_pos, event, widget_tree):
        date = self.core.call_success(
            I18n.i18n_parse_date_short, gtk_entry.get_text()
        )
        if date is None:
            return
        widget_tree.get_object("calendar_calendar").select_month(
            date.month - 1, date.year
        )
        widget_tree.get_object("calendar_calendar").select_day(
            date.day
        )
        widget_tree.get_object("calendar_popover").set_visible(True)

    def _update_date(self, gtk_calendar, gtk_entry, widget_tree):
        date = widget_tree.get_object("calendar_calendar").get_date()
        date = datetime.datetime(year=date[0], month=date[1] + 1, day=date[2])
        date = self.core.call_success(I18n.i18n_date_short, date)
        gtk_entry.set_text(date)
        widget_tree.get_object("calendar_popover").set_visible(False)
