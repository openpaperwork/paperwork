import abc


class GtkApp(abc.ABC):
    @abc.abstractmethod
    def gtk_get_app(self):
        ...


class GtkInit(abc.ABC):
    @abc.abstractmethod
    def gtk_init(self, main_func, *args):
        ...


class GtkResources(abc.ABC):
    @abc.abstractmethod
    def gtk_load_widget_tree(self, pkg, filename):
        ...

    @abc.abstractmethod
    def gtk_load_css(self, pkg, filename):
        ...

    @abc.abstractmethod
    def gtk_load_pixbuf(self, pkg, filename):
        ...

    @abc.abstractmethod
    def gtk_fix_headerbar_buttons(self, headerbar):
        ...
