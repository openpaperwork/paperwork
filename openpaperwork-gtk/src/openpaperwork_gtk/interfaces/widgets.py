import abc


class WidgetActivity(abc.ABC):
    @abc.abstractmethod
    def on_widget_busyness_changed(self, widget, busy):
        ...


class GtkCalendarWidget(abc.ABC):
    @abc.abstractmethod
    def add_popover(self, gtk_entry):
        ...


class GtkProgressWidget(abc.ABC):
    @abc.abstractmethod
    def make_widget(self):
        ...


class GtkChartLines(abc.ABC):
    def gtk_charts_lines_get(self, liststore, *args, **kwargs):
        ...
