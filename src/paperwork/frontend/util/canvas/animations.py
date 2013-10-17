from gi.repository import Gtk

from paperwork.frontend.util.canvas.drawers import Drawer

class SpinnerAnimation(Drawer):
    ICON_SIZE = 48

    layer = Drawer.SPINNER_LAYER

    def __init__(self, position):
        self.position = position
        self.size = (self.ICON_SIZE, self.ICON_SIZE)

        icon_theme = Gtk.IconTheme.get_default()
        icon_info = icon_theme.lookup_icon("process-working", self.ICON_SIZE,
                                           Gtk.IconLookupFlags.NO_SVG)
        self.icon_pixbuf = icon_info.load_icon()
