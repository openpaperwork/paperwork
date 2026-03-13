from openpaperwork_core.interfaces.app import App
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources

from paperwork_gtk.interfaces.home import PaperworkHome
from paperwork_gtk.interfaces.icon import Icon
from paperwork_gtk.interfaces.main_window import MainWindow


class Plugin(
    openpaperwork_core.PluginBase,
    PaperworkHome,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=App,
                defaults=['paperwork_backend.app'],
            ),
            openpaperwork_core.Dependency(
                interface=MainWindow,
                defaults=['paperwork_gtk.mainwindow.window'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
            openpaperwork_core.Dependency(
                interface=Icon,
                defaults=['paperwork_gtk.icon'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.home", "home.glade"
        )
        if widget_tree is None:
            return

        logo_pixbuf = self.core.call_success(
            Icon.icon_get_pixbuf, "paperwork", 128
        )
        logo_widget = widget_tree.get_object("paperwork_logo")
        logo_widget.set_from_pixbuf(logo_pixbuf)

        logo_text = widget_tree.get_object("main_label")
        logo_text.set_text("Paperwork {}".format(
            self.core.call_success(App.app_get_version)
        ))

        self.core.call_all(
            MainWindow.mainwindow_add, side="right", name="home", prio=100000,
            header=None,
            body=widget_tree.get_object("home")
        )
