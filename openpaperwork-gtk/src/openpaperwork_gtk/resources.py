import gettext
import logging
import os
import re

if os.name == "nt":
    import webbrowser
    import xml.etree.ElementTree


LOGGER = logging.getLogger(__name__)

GI_AVAILABLE = False
GDK_PIXBUF_AVAILABLE = False
GTK_AVAILABLE = False
HDY_AVAILABLE = False


try:
    import gi
    GI_AVAILABLE = True
except (ValueError, ImportError) as exc:
    LOGGER.error("Failed to load Gobject-Introspection", exc_info=exc)

if GI_AVAILABLE:
    try:
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import GdkPixbuf
        GDK_PIXBUF_AVAILABLE = True
    except (ValueError, ImportError) as exc:
        LOGGER.error("Failed to load GDK-Pixbuf", exc_info=exc)

    try:
        gi.require_version('Gdk', '3.0')
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gdk
        from gi.repository import Gtk
        GTK_AVAILABLE = True
    except (ImportError, ValueError) as exc:
        LOGGER.error("Failed to load Gtk", exc_info=exc)

    try:
        gi.require_version('Handy', '1')
        from gi.repository import Handy
        HDY_AVAILABLE = True
    except (ImportError, ValueError) as exc:
        LOGGER.error("Failed to load Handy", exc_info=exc)


import openpaperwork_core  # noqa: E402
import openpaperwork_core.deps  # noqa: E402

from . import deps  # noqa: E402


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.cache = {}

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_resources'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'l10n_init',
                'defaults': [
                    'openpaperwork_core.l10n.python',
                    'openpaperwork_gtk.l10n',
                ],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not HDY_AVAILABLE:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to initalize Libhandy")
            return
        Handy.init()

    def chkdeps(self, out: dict):
        if not GDK_PIXBUF_AVAILABLE:
            out['gdk_pixbuf'].update(deps.GDK_PIXBUF)
        if not GTK_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
            out['gtk'].update(deps.GTK)
        if not HDY_AVAILABLE:
            out['hdy'].update(deps.HDY)

    @staticmethod
    def _translate_xml(xml_str):
        root = xml.etree.ElementTree.fromstring(xml_str)

        translation_domain = "openpaperwork_gtk"
        if 'domain' in root.attrib:
            translation_domain = root.attrib['domain']

        labels = root.findall('.//*[@translatable="yes"]')
        for label in labels:
            label.text = gettext.dgettext(translation_domain, label.text)

        out = xml.etree.ElementTree.tostring(root, encoding='UTF-8')
        return out.decode('utf-8')

    @staticmethod
    def _windows_fix_widgets(widget_tree):
        def open_uri(uri):

            # XXX(Jflesch): Seems we get some garbarge in the URI sometimes ?!
            uri = uri.replace("\u202f", "")

            LOGGER.info("Opening URI [%s]", uri)
            webbrowser.open(uri)

        for obj in widget_tree.get_objects():
            if isinstance(obj, Gtk.LinkButton):
                obj.connect(
                    "clicked",
                    lambda button: open_uri(button.get_uri())
                )
            elif (isinstance(obj, Gtk.AboutDialog) or
                    isinstance(obj, Gtk.Label)):
                obj.connect(
                    "activate-link",
                    lambda widget, uri: open_uri(uri)
                )

    def gtk_load_widget_tree(self, pkg, filename):
        """
        Load a .glade file

        Arguments:
            pkg -- Python package name
            filename -- css file name to load

        Returns:
            GTK Widget Tree
        """

        if not GTK_AVAILABLE or not HDY_AVAILABLE:
            LOGGER.error(
                "gtk_load_widget_tree(): GTK|Libhandy is not available"
            )
            return None

        LOGGER.debug("Loading GTK widgets from %s:%s", pkg, filename)

        screen = Gdk.Screen.get_default()
        if screen is None:
            LOGGER.warning(
                "Cannot load widget tree: Gdk.Screen.get_default()"
                " returned None"
            )
            return None

        k = (pkg, filename)
        if k not in self.cache:
            try:
                file_path_ctx = self.core.call_success(
                    "resources_get_file", pkg, filename
                )
                with file_path_ctx as file_path:
                    file_url = self.core.call_success("fs_safe", file_path)
                    with self.core.call_success("fs_open", file_url, 'r') as fd:
                        xml = fd.read()
                if os.name == "nt":
                    # WORKAROUND(Jflesch):
                    # for some reason,
                    # Gtk.Builder.new_from_file()/new_from_string doesn't
                    # translate on Windows
                    xml = self._translate_xml(xml)
                self.cache[k] = xml
            except Exception:
                LOGGER.error(
                    "Failed to load widget tree from file %s:%s",
                    pkg, filename
                )
                raise

        try:
            content = self.cache[k]
            widget_tree = Gtk.Builder.new_from_string(content, -1)
            if os.name == "nt":
                self._windows_fix_widgets(widget_tree)
            return widget_tree
        except Exception:
            LOGGER.error("Failed to load widget tree %s:%s", pkg, filename)
            raise

    def gtk_load_css(self, pkg, filename):
        """
        Load a .css file

        Arguments:
            pkg -- Python package name
            filename -- css file name to load.
        """
        if not GTK_AVAILABLE or not HDY_AVAILABLE:
            LOGGER.error("gtk_load_css(): GTK|Libhandy is not available")
            return None

        LOGGER.debug("Loading CSS from %s:%s", pkg, filename)

        k = (pkg, filename)

        if k not in self.cache:
            try:
                file_path_ctx = self.core.call_success(
                    "resources_get_file", pkg, filename
                )
                with file_path_ctx as file_path:
                    file_url = self.core.call_success("fs_safe", file_path)
                    with self.core.call_success("fs_open", file_url, 'rb') as fd:
                        self.cache[k] = fd.read()
            except Exception:
                LOGGER.error("Failed to load CSS file %s:%s", pkg, filename)
                raise

        try:
            content = self.cache[k]

            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(content)

            screen = Gdk.Screen.get_default()
            if screen is None:
                LOGGER.warning(
                    "Cannot apply CSS: Gdk.Screen.get_default()"
                    " returned None"
                )
                return None

            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception:
            LOGGER.error("Failed to load CSS %s:%s", pkg, filename)
            raise

        return True

    def gtk_load_pixbuf(self, pkg, filename):
        file_path_ctx = self.core.call_success("resources_get_file", pkg, filename)
        if file_path_ctx is None:
            return None
        with file_path_ctx as file_path:
            return GdkPixbuf.Pixbuf.new_from_file(str(file_path.resolve()))

    def gtk_fix_headerbar_buttons(self, headerbar):
        settings = Gtk.Settings.get_default()
        default_layout = settings.get_property("gtk-decoration-layout")
        default_layout = re.split("[:,]", default_layout)

        # disable the elements that are not enabled globally
        layout = headerbar.get_decoration_layout().split(":", 1)
        layout = [side.split(",") for side in layout]
        layout = ":".join([
            ",".join([
                element for element in side
                if element in default_layout
            ])
            for side in layout
        ])

        headerbar.set_decoration_layout(layout)
