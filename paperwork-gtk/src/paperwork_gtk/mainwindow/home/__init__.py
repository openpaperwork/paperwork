import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ['home']

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': 'app',
                'defaults': ['paperwork_backend.app'],
            },
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'icon',
                'defaults': ['paperwork_gtk.icon'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.home", "home.glade"
        )
        if widget_tree is None:
            return

        logo_pixbuf = self.core.call_success(
            "icon_get_pixbuf", "paperwork", 128
        )
        logo_widget = widget_tree.get_object("paperwork_logo")
        logo_widget.set_from_pixbuf(logo_pixbuf)

        logo_text = widget_tree.get_object("main_label")
        logo_text.set_text("Paperwork {}".format(
            self.core.call_success("app_get_version")
        ))

        self.core.call_all(
            "mainwindow_add", side="right", name="home", prio=100000,
            header=None,
            body=widget_tree.get_object("home")
        )
