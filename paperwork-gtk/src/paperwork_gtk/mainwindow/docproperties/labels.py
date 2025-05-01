import enum
import logging
import re

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

from openpaperwork_core.interfaces.chkdeps import Chkdeps
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.i18n import I18n
from openpaperwork_core.interfaces.mainloop import Mainloop
from openpaperwork_core.interfaces.progress import ProgressListener
import openpaperwork_core

from openpaperwork_gtk.interfaces.colors import GtkColors
from openpaperwork_gtk.interfaces.dialogs import (
    GtkSingleEntryDialog,
    GtkSingleEntryDialogListener,
    GtkYesNoDialog
)
from openpaperwork_gtk.interfaces.dialogs import GtkYesNoDialogListener
from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.gtk_window import GtkWindowListener
from openpaperwork_gtk.interfaces.screenshot import (
    Screenshot,
    ScreenshotProvider
)
import openpaperwork_gtk.deps

from paperwork_backend.interfaces.doc_labels import DocLabelColors
from paperwork_backend.interfaces.doc_labels import DocLabelListener
from paperwork_backend.interfaces.doc_labels import DocLabels
from paperwork_backend.interfaces.doc_storage import DocStorage
from paperwork_backend.interfaces.doc_transactions import DocTransactionFactory
from paperwork_backend.interfaces.sync import Syncable
import paperwork_backend.sync

from paperwork_gtk.interfaces.doc_properties import DocPropertiesComponent
from paperwork_gtk import _


LOGGER = logging.getLogger(__name__)

# forbid:
# - empty strings
# - strings that contain a comma
RE_FORBIDDEN_LABELS = re.compile("(^$|.*,.*)")


class LabelChange(enum.Enum):
    UNCHANGED = 0
    ADDED = 1
    REMOVED = 2


class LabelAction:
    def __init__(self, current_state):
        # current_state == None for multiple document selection
        self.current_state = current_state
        self.change = LabelChange.UNCHANGED

    def on_change(self):
        if self.current_state is None:

            # multi-docs mode : rotate over the 3 possible change values
            if self.change == LabelChange.UNCHANGED:
                self.change = LabelChange.ADDED
            elif self.change == LabelChange.ADDED:
                self.change = LabelChange.REMOVED
            elif self.change == LabelChange.REMOVED:
                self.change = LabelChange.UNCHANGED

        else:

            # single-doc mode

            if not self.current_state:

                if self.change == LabelChange.UNCHANGED:
                    self.change = LabelChange.ADDED
                else:
                    self.change = LabelChange.UNCHANGED

            else:

                if self.change == LabelChange.UNCHANGED:
                    self.change = LabelChange.REMOVED
                else:
                    self.change = LabelChange.UNCHANGED

    def get_image(self):
        if self.change == LabelChange.ADDED:
            return "list-add-symbolic"
        elif self.change == LabelChange.REMOVED:
            return "list-remove-symbolic"
        else:
            if self.current_state:
                return "object-select-symbolic"
            return None

    def __str__(self):
        return str((self.change, self.current_state))


class LabelEditor:
    def __init__(self, plugin):
        super().__init__()
        self.core = plugin.core
        self.plugin = plugin

        self.active_docs = []

        # self.changed_labels contains the label that have been modified
        # (color or text)
        self.changed_labels = {}

        # self.toggled_labels indicates the labels that have been selected or
        # unselected (value = LabelAction, depending on whether they are
        # now selected or not)
        self.toggled_labels = {}

        # self.new_labels contains the labels that user has just created
        # (but are not yet applied on any document)
        self.new_labels = set()

        # self.deleted_labels contains the labels that the user wants to
        # remove from *all* the documents.
        self.deleted_labels = set()

        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docproperties", "labels.glade"
        )
        color_widget = self.widget_tree.get_object("new_label_color")
        color_widget.set_rgba(self.core.call_success(
            GtkColors.gtk_theme_get_color, "theme_bg_color"
        ))

        self.widget_tree.get_object("new_label_button").connect(
            "clicked", self._on_new_label
        )
        new_label_entry = self.widget_tree.get_object("new_label_entry")
        new_label_entry.connect("activate", self._on_new_label)
        new_label_entry.connect("changed", self._on_label_txt_changed)

    def _update_button_img(self, toggle, label_action):
        img = label_action.get_image()
        if img is not None:
            image = Gtk.Image.new_from_icon_name(img, Gtk.IconSize.MENU)
        else:
            image = Gtk.Image()
        toggle.set_image(image)

    def _refresh_list(self):
        listbox = self.widget_tree.get_object("listbox_labels")
        for widget in list(listbox.get_children()):
            listbox.remove(widget)

        doc_labels = None
        if len(self.active_docs) == 1:
            doc_labels = set()
            active_doc = list(self.active_docs)[0]
            self.core.call_all(
                DocLabels.doc_get_labels_by_url, doc_labels, active_doc[1]
            )

        labels = set()
        self.core.call_all(DocLabels.labels_get_all, labels)
        if doc_labels is not None:
            labels.update(doc_labels)

        labels = [
            (
                self.core.call_success(I18n.i18n_strip_accents, label[0].lower()),
                label[0],
                label[1]
            ) for label in labels
        ]
        labels.sort()
        labels = [(label[1], label[2]) for label in labels]

        if doc_labels is not None:
            doc_labels = {doc_label[0] for doc_label in doc_labels}
        for old_label in labels:
            if old_label in self.changed_labels:
                new_label = self.changed_labels[old_label]
            else:
                new_label = old_label

            if old_label in self.deleted_labels:
                continue

            if old_label in self.toggled_labels:
                label_action = self.toggled_labels[old_label]
            else:
                if doc_labels is None:
                    active = None
                else:
                    active = old_label[0] in doc_labels
                label_action = LabelAction(active)

            widget_tree_label = self.core.call_success(
                GtkResources.gtk_load_widget_tree,
                "paperwork_gtk.mainwindow.docproperties", "label.glade"
            )
            button = widget_tree_label.get_object("label_label")
            button.set_label(new_label[0])
            button.connect("clicked", self._on_label_button_clicked, old_label)

            toggle = widget_tree_label.get_object("toggle_button")
            toggle.set_sensitive(True)
            self._update_button_img(toggle, label_action)
            toggle.connect("clicked", self._on_toggle, old_label, label_action)

            color = self.core.call_success(DocLabelColors.label_color_to_rgb, new_label[1])
            color_button = widget_tree_label.get_object("color_button")
            color_button.set_sensitive(old_label not in self.new_labels)
            color_button.set_rgba(Gdk.RGBA(color[0], color[1], color[2], 1.0))
            color_button.connect(
                "color-set", self._on_color_changed, old_label
            )

            delete = widget_tree_label.get_object("delete_button")
            delete.connect("clicked", self._on_delete, old_label)

            listbox.add(widget_tree_label.get_object("label_row"))

        new_labels = list(self.new_labels)
        new_labels.sort()
        for label in new_labels:
            widget_tree_label = self.core.call_success(
                GtkResources.gtk_load_widget_tree,
                "paperwork_gtk.mainwindow.docproperties", "label.glade"
            )
            button = widget_tree_label.get_object("label_label")
            button.set_label(label[0])
            button.set_sensitive(False)

            toggle = widget_tree_label.get_object("toggle_button")
            toggle.set_sensitive(False)
            image = Gtk.Image.new_from_icon_name(
                "list-add-symbolic", Gtk.IconSize.MENU
            )
            toggle.set_image(image)

            color = self.core.call_success(DocLabelColors.label_color_to_rgb, label[1])
            color_button = widget_tree_label.get_object("color_button")
            color_button.set_sensitive(True)
            color_button.set_rgba(Gdk.RGBA(color[0], color[1], color[2], 1.0))
            color_button.connect(
                "color-set", self._on_new_color_changed, label
            )

            delete = widget_tree_label.get_object("delete_button")
            delete.connect("clicked", self._on_new_delete, label)

            listbox.add(widget_tree_label.get_object("label_row"))

        listbox.add(self.widget_tree.get_object("row_add_label"))

    def _on_label_button_clicked(self, label_button, label):
        original_label = label
        if label in self.changed_labels:
            label = self.changed_labels[label]
        self.core.call_success(
            GtkSingleEntryDialog.gtk_show_dialog_single_entry,
            self.plugin, _("Renaming label"),
            label[0], self, label_button, original_label, label
        )

    def on_label_rename_response(
            self, new_label_txt, label_button, original_label, label):
        new_label_txt = new_label_txt.strip()

        if not self._check_label_name(new_label_txt):
            return

        LOGGER.info("Renaming label %s --> %s", label, new_label_txt)
        self.changed_labels[original_label] = (new_label_txt, label[1])

        label_button.set_label(new_label_txt)

    def _on_toggle(self, button, label, label_action):
        label_action.on_change()
        self._update_button_img(button, label_action)
        self.toggled_labels[label] = label_action

    def _on_color_changed(self, button, original_label):
        color = button.get_rgba()
        color = (color.red, color.green, color.blue)
        color = self.core.call_success(DocLabelColors.label_color_from_rgb, color)

        label = original_label
        if original_label in self.changed_labels:
            label = self.changed_labels[original_label]
        new_label = (label[0], color)

        self.changed_labels[original_label] = new_label

    def _on_new_color_changed(self, button, original_label):
        self.new_labels.remove(original_label)
        color = button.get_rgba()
        color = (color.red, color.green, color.blue)
        color = self.core.call_success(DocLabelColors.label_color_from_rgb, color)
        new_label = (original_label[0], color)
        self.new_labels.add(new_label)
        self._refresh_list()

    def _on_delete(self, button, original_label):
        self.core.call_all(
            GtkYesNoDialog.gtk_show_dialog_yes_no,
            self,
            _(
                "Are you sure you want to delete label '%s'"
                " from ALL documents ?"
            ) % (original_label,),
            original_label,
        )

    def on_dialog_yes_no_reply(self, origin, response, *args, **kwargs):
        if origin is not self:
            return
        if not response:
            LOGGER.info("Label delete canceled")
            return
        (original_label,) = args
        LOGGER.info("Will delete label %s on all documents", original_label)
        self.deleted_labels.add(original_label)
        self._refresh_list()

    def _on_new_delete(self, button, label):
        self.new_labels.remove(label)
        self._refresh_list()

    def _check_label_name(self, label_name):
        all_labels = set()
        self.core.call_all(DocLabels.labels_get_all, all_labels)
        for label in set(all_labels):
            if label in self.changed_labels:
                all_labels.add(self.changed_labels[label])
        all_labels.update(self.new_labels)
        all_labels = {label[0] for label in all_labels}

        if label_name in all_labels:
            return False

        if RE_FORBIDDEN_LABELS.match(label_name):
            return False

        return True

    def _on_label_txt_changed(self, *args, **kwargs):
        entry = self.widget_tree.get_object("new_label_entry")
        button = self.widget_tree.get_object("new_label_button")
        txt = entry.get_text().strip()

        valid = self._check_label_name(txt)

        button.set_sensitive(valid)
        if valid or txt == "":
            self.core.call_all(GtkColors.gtk_entry_reset_colors, entry)
        else:
            self.core.call_all(GtkColors.gtk_entry_set_colors, entry)

    def _on_new_label(self, *args, **kwargs):
        text = self.widget_tree.get_object("new_label_entry").get_text()
        text = text.strip()
        if text == "":
            LOGGER.info("New label requested, but no text provided")
            return

        color_widget = self.widget_tree.get_object("new_label_color")

        color = color_widget.get_rgba()
        color = (color.red, color.green, color.blue)
        color = self.core.call_success(DocLabelColors.label_color_from_rgb, color)

        self.new_labels.add((text, color))
        self._refresh_list()

        # reset fields
        self.widget_tree.get_object("new_label_entry").set_text("")
        color_widget.set_rgba(self.core.call_success(
            GtkColors.gtk_theme_get_color, "theme_bg_color"
        ))

    def _make_new_labels(self, out, doc_id, doc_url):
        if len(self.new_labels) <= 0:
            return
        for label in self.new_labels:
            self.core.call_success(
                DocLabels.doc_add_label_by_url, doc_url, label[0], label[1]
            )
        out.upd_docs.add(doc_id)

    def _make_label_updates(self, out):
        if len(self.changed_labels) <= 0:
            return

        all_docs = []
        self.core.call_all(DocStorage.storage_get_all_docs, all_docs)
        all_docs = set(all_docs)

        current = 0
        total = len(self.changed_labels) * len(all_docs)

        for (doc_id, doc_url) in all_docs:
            for (old_label, new_label) in self.changed_labels.items():
                LOGGER.info(
                    "Changing label %s into %s on document %s",
                    old_label, new_label, doc_id
                )
                self.core.call_all(
                    ProgressListener.on_progress, "label_upd", current / total,
                    _(
                        "Changing label {old_label} into {new_label}"
                        " on document {doc_id}"
                    ).format(
                        old_label=old_label, new_label=new_label, doc_id=doc_id
                    )
                )
                current += 1
                doc_labels = set()
                self.core.call_all(
                    DocLabels.doc_get_labels_by_url, doc_labels, doc_url
                )
                if old_label not in doc_labels:
                    continue
                out.upd_docs.add(doc_id)
                self.core.call_all(
                    DocLabels.doc_remove_label_by_url, doc_url, old_label[0]
                )
                self.core.call_success(
                    DocLabels.doc_add_label_by_url, doc_url,
                    new_label[0], new_label[1]
                )
        self.core.call_all(ProgressListener.on_progress, "label_upd", 1.0)

    def _make_label_toggling(self, out, doc_id, doc_url):
        if len(self.toggled_labels) <= 0:
            return

        for (label, action) in self.toggled_labels.items():
            doc_labels = set()
            self.core.call_all(DocLabels.doc_get_labels_by_url, doc_labels, doc_url)

            if action.change == LabelChange.ADDED:
                if label in doc_labels:
                    continue
                self.core.call_success(
                    DocLabels.doc_add_label_by_url, doc_url, label[0], label[1]
                )
                out.upd_docs.add(doc_id)
            elif action.change == LabelChange.REMOVED:
                if label not in doc_labels:
                    continue
                self.core.call_all(
                    DocLabels.doc_remove_label_by_url, doc_url, label[0]
                )
                out.upd_docs.add(doc_id)

    def _make_label_deletions(self, out):
        if len(self.deleted_labels) <= 0:
            return

        all_docs = []
        self.core.call_all(DocStorage.storage_get_all_docs, all_docs)
        all_docs = set(all_docs)

        current = 0
        total = len(self.deleted_labels) * len(all_docs)

        for (doc_id, doc_url) in all_docs:
            for old_label in self.deleted_labels:
                LOGGER.info(
                    "Deleting label %s from document %s",
                    old_label, doc_id
                )
                self.core.call_all(
                    ProgressListener.on_progress, "label_del", current / total,
                    _(
                        "Deleting label {old_label} from document {doc_id}"
                    ).format(old_label=old_label, doc_id=doc_id)
                )
                current += 1
                doc_labels = set()
                self.core.call_all(
                    DocLabels.doc_get_labels_by_url, doc_labels, doc_url
                )
                if old_label not in doc_labels:
                    continue
                out.upd_docs.add(doc_id)
                self.core.call_all(
                    DocLabels.doc_remove_label_by_url, doc_url, old_label[0]
                )
        self.core.call_all(ProgressListener.on_progress, "label_del", 1.0)

    def set_active_doc(self, doc_id, doc_url):
        self.set_active_docs({(doc_id, doc_url)})

    def set_active_docs(self, docs: set):
        self.active_docs = docs
        self.changed_labels = {}
        self.toggled_labels = {}
        self.new_labels = set()
        self.deleted_labels = set()
        new_label_entry = self.widget_tree.get_object("new_label_entry")
        new_label_entry.set_text("")

        self._refresh_list()

    def apply_changes(self, out):
        LOGGER.info("Selected/Unselected labels: %s", self.toggled_labels)
        LOGGER.info("Modified labels: %s", self.changed_labels)
        LOGGER.info("New labels: %s", self.new_labels)
        LOGGER.info("Deleted labels: %s", self.deleted_labels)

        if len(self.active_docs) == 1:
            # The document may have been renamed: use out.doc_id instead of
            # self.active_docs
            doc_id = out.doc_id
            doc_url = self.core.call_success(DocStorage.doc_id_to_url, doc_id)
            self.active_docs = {(doc_id, doc_url)}

        for (doc_id, doc_url) in self.active_docs:
            LOGGER.info("Updating document %s", doc_id)
            self._make_label_toggling(out, doc_id, doc_url)
            self._make_new_labels(out, doc_id, doc_url)

        if len(self.changed_labels) <= 0 and len(self.deleted_labels) <= 0:
            return
        self._make_label_deletions(out)
        self._make_label_updates(out)

    def cancel_changes(self):
        self.set_active_docs(self.active_docs)


class Plugin(
    openpaperwork_core.PluginBase,
    Chkdeps,
    DocLabelListener,
    DocPropertiesComponent,
    DocTransactionFactory,
    GtkSingleEntryDialogListener,
    GtkYesNoDialogListener,
    GtkWindowListener,
    ScreenshotProvider,
    Syncable,
):
    PRIORITY = 1000

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocLabels,
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                "interface": DocLabelColors,
                "defaults": ["paperwork_backend.model.labels"],
            },
            {
                'interface': DocStorage,
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                "interface": Fs,
                "defaults": ["openpaperwork_gtk.fs.gio"],
            },
            {
                'interface': GtkColors,
                'defaults': ['openpaperwork_gtk.colors'],
            },
            {
                'interface': GtkYesNoDialog,
                'defaults': ['openpaperwork_gtk.dialogs.yes_no'],
            },
            {
                "interface": GtkSingleEntryDialog,
                'defaults': ['openpaperwork_gtk.dialogs.single_entry'],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                "interface": Mainloop,
                "defaults": ["openpaperwork_gtk.mainloop.glib"],
            },
            {
                'interface': I18n,
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                'interface': Screenshot,
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.windows = []
        self.editors = []
        if not GTK_AVAILABLE:
            # chkdeps() must still be callable
            return

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def doc_properties_components_get(self, out: list, multiple_docs=False):
        editor = LabelEditor(self)
        self.editors.append(editor)
        out.append(editor.widget_tree.get_object("listbox_global"))

    def on_dialog_yes_no_reply(self, origin, response, *args, **kwargs):
        for editor in self.editors:
            editor.on_dialog_yes_no_reply(origin, response, *args, **kwargs)

    def doc_properties_components_set_active_doc(self, doc_id, doc_url):
        for editor in self.editors:
            editor.set_active_doc(doc_id, doc_url)

    def doc_properties_components_set_active_docs(self, docs: set):
        for editor in self.editors:
            editor.set_active_docs(docs)

    def doc_properties_components_apply_changes(self, out):
        for editor in self.editors:
            editor.apply_changes(out)

    def doc_properties_components_cancel_changes(self):
        for editor in self.editors:
            editor.cancel_changes()

    def on_dialog_single_entry_reply(
            self, parent, r, new_value, *args, **kwargs):
        if parent is not self:
            return
        if not r:
            return
        editor = args[0]
        args = args[1:]
        editor.on_label_rename_response(new_value, *args, **kwargs)

    def doc_transaction_start(self, out: list, total_expected=-1):
        class RefreshTransaction(paperwork_backend.sync.BaseTransaction):
            priority = -100000

            def commit(s):
                for editor in self.editors:
                    self.core.call_one(
                        Mainloop.mainloop_schedule, editor._refresh_list
                    )

        out.append(RefreshTransaction(self.core, total_expected))

    @openpaperwork_core.noop
    def sync(self, promises: list):
        pass

    @openpaperwork_core.noop
    def on_label_loading_start(self):
        pass

    def on_label_loading_end(self):
        for editor in self.editors:
            editor._refresh_list()

    def screenshot_snap_all_doc_widgets(self, out_dir):
        for editor in self.editors:
            self.core.call_success(
                Screenshot.screenshot_snap_widget,
                editor.widget_tree.get_object("listbox_global"),
                self.core.call_success(
                    Fs.fs_join, out_dir, "doc_labels.png"
                ),
                margins=(10, 10, 10, -400)
            )
            self.core.call_success(
                Screenshot.screenshot_snap_widget,
                editor.widget_tree.get_object("new_label_button"),
                self.core.call_success(
                    Fs.fs_join, out_dir, "doc_new_label.png"
                ),
                margins=(400, 50, 50, 50)
            )
