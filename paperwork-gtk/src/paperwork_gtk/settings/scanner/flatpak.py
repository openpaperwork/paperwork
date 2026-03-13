from openpaperwork_core.interfaces.flatpak import Flatpak
import openpaperwork_core

from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener

from paperwork_gtk.interfaces.settings import GtkSettingsScannerExtra


INSTRUCTIONS = {
    # 'Arch Linux / Manjaro / …': (
    #     "# TODO\n"
    # ),
    'Debian / Ubuntu / Mint / …': (
        "sudo apt install sane-utils\n"
        "sudo sh -c \"echo 127.0.0.1 >> /etc/sane.d/saned.conf\"\n"
        "sudo systemctl enable saned.socket\n"
        "sudo systemctl start saned.socket\n"
        "sudo adduser saned plugdev\n"
        "sudo adduser saned scanner\n"
        "sudo adduser saned lp\n"
        "# reboot\n"
        "\n"
        "# If your scanner is still not recognized, please check\n"
        "# https://gitlab.gnome.org/World/OpenPaperwork/paperwork/-/blob"
        "/develop/doc/install.flatpak.markdown#faq\n"
    ),
    'Fedora / CentOS / RHEL / …': (
        "sudo dnf install libinsane sane-backends-daemon\n"
        "sudo sh -c \"echo 127.0.0.1 >> /etc/sane.d/saned.conf\"\n"
        "sudo systemctl enable saned.socket\n"
        "sudo systemctl start saned.socket\n"
    ),
}


class Plugin(openpaperwork_core.PluginBase, GtkWindowListener, GtkSettingsScannerExtra):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=Flatpak,
                defaults=['openpaperwork_core.flatpak'],
            ),
            openpaperwork_core.Dependency(
                interface=GtkResources,
                defaults=['openpaperwork_gtk.resources'],
            ),
        ]

    def __init__(self, core):
        super().__init__(core)
        self.windows = []

    def settings_scanner_get_extra_widget(self):
        if not self.core.call_success(Flatpak.is_in_flatpak):
            return None

        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree, "paperwork_gtk.settings.scanner",
            "flatpak.glade"
        )
        if widget_tree is None:
            return None
        button = widget_tree.get_object("button_flatpak_info")
        button.connect("clicked", self._on_clicked)
        return button

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _on_clicked(self, button):
        widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree, "paperwork_gtk.settings.scanner",
            "flatpak.glade"
        )
        if widget_tree is None:
            return

        dialog = widget_tree.get_object("flatpak_info_dialog")
        dialog.set_transient_for(self.windows[-1])
        dialog.set_modal(True)
        dialog.connect("response", self._on_close)
        dialog.connect("destroy", self._on_close)
        dialog.set_visible(True)

        selector = widget_tree.get_object("flatpak_info_selector")
        for k in sorted(INSTRUCTIONS.keys()):
            selector.append_text(k)

        selector.connect("changed", self._on_changed, widget_tree)
        selector.set_active(0)
        self._on_changed(selector, widget_tree)

    def _on_changed(self, selector, widget_tree):
        selected = selector.get_active_text()
        instruction = INSTRUCTIONS[selected]
        txt_buffer = widget_tree.get_object("textbuffer_instructions")
        txt_buffer.set_text(instruction)

    def _on_close(self, dialog, *args, **kwargs):
        dialog.set_visible(False)
