import abc


class GtkColors(abc.ABC):
    @abc.abstractmethod
    def gtk_entry_set_colors(self, gtk_entry, fg="black", bg="#CC3030"):
        ...

    @abc.abstractmethod
    def gtk_entry_reset_colors(self, gtk_entry):
        ...

    @abc.abstractmethod
    def gtk_theme_get_color(self, color_name):
        ...
