import logging

from openpaperwork_core.interfaces.i18n import I18n
import openpaperwork_core

from openpaperwork_gtk.interfaces.colors import GtkColors
from openpaperwork_gtk.interfaces.gtk import GtkResources
from openpaperwork_gtk.interfaces.widgets import GtkCalendarWidget

from paperwork_backend.interfaces.doc_storage import DocStorage

from paperwork_gtk.interfaces.doc_properties import DocPropertiesComponent


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    DocPropertiesComponent,
):
    PRIORITY = 10000

    @classmethod
    def get_deps(cls):
        return [
            {
                'interface': DocStorage,
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': GtkCalendarWidget,
                'defaults': ['openpaperwork_gtk.widgets.calendar'],
            },
            {
                'interface': GtkColors,
                'defaults': ['openpaperwork_gtk.colors'],
            },
            {
                'interface': GtkResources,
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': I18n,
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.widget_tree = None
        self.active_doc = None

    def doc_properties_components_get(self, out: list, multiple_docs=False):
        if multiple_docs:
            return
        self.widget_tree = self.core.call_success(
            GtkResources.gtk_load_widget_tree,
            "paperwork_gtk.mainwindow.docproperties", "name.glade"
        )

        self.core.call_all(
            GtkCalendarWidget.add_popover,
            self.widget_tree.get_object("docname_entry")
        )

        self.widget_tree.get_object("docname_entry").connect(
            "changed", self._on_doc_date_changed
        )

        out.append(self.widget_tree.get_object("docname"))

    def doc_properties_components_set_active_doc(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

        doc_date = self.core.call_success(DocStorage.doc_get_date_by_id, doc_id)
        if doc_date is not None:
            doc_txt = self.core.call_success(I18n.i18n_date_short, doc_date)
        else:
            doc_txt = doc_id
        self.widget_tree.get_object("docname_entry").set_text(doc_txt)

    def _check_doc_id(self, doc_id):
        if doc_id == "":
            return False
        for forbidden in ["/", "\\", "?", "*"]:
            if forbidden in doc_id:
                return False
        return True

    def _on_doc_date_changed(self, gtk_entry):
        txt = gtk_entry.get_text()
        txt = txt.strip()
        r = self.core.call_success(I18n.i18n_parse_date_short, txt)
        if r is not None:
            self.core.call_all(GtkColors.gtk_entry_reset_colors, gtk_entry)
        elif not self._check_doc_id(txt):
            self.core.call_all(GtkColors.gtk_entry_set_colors, gtk_entry, bg="#ff0000")
        else:
            self.core.call_all(GtkColors.gtk_entry_set_colors, gtk_entry, bg="#ee9000")

    def doc_properties_components_apply_changes(self, out):
        if out.multiple_docs:
            return

        doc_id = self.widget_tree.get_object("docname_entry").get_text()
        doc_id = doc_id.strip()

        doc_date = self.core.call_success(I18n.i18n_parse_date_short, doc_id)
        if doc_date is not None:
            doc_id = self.core.call_success(DocStorage.doc_get_id_by_date, doc_date)
        elif not self._check_doc_id(doc_id):
            LOGGER.error(
                "Invalid document id specified. Won't rename the document"
            )
            return
        else:
            LOGGER.warning(
                "Failed to parse document date: %s. Using as is", doc_id
            )

        orig_id = out.doc_id
        orig_date = self.core.call_success(DocStorage.doc_get_date_by_id, orig_id)
        if orig_date is not None:
            orig_date = orig_date.date()
        else:
            orig_date = orig_id

        dest_id = doc_id
        dest_date = self.core.call_success(DocStorage.doc_get_date_by_id, dest_id)
        if dest_date is not None:
            dest_date = dest_date.date()
        else:
            dest_date = dest_id

        if orig_date == dest_date:
            return

        LOGGER.info("Previous document id: %s (%s)", orig_id, orig_date)
        LOGGER.info("New document id: %s (%s)", dest_id, dest_date)

        orig_url = self.core.call_success(DocStorage.doc_id_to_url, orig_id)
        dest_url = self.core.call_success(
            DocStorage.doc_id_to_url, dest_id, existing=False
        )

        LOGGER.info("Renaming document %s into %s", orig_id, dest_id)
        dest_url = self.core.call_success(
            DocStorage.doc_rename_by_url, orig_url, dest_url
        )
        if not dest_url:
            LOGGER.warning("Renaming %s into %s failed", orig_id, dest_id)
            return
        dest_id = self.core.call_success(DocStorage.doc_url_to_id, dest_url)

        out.del_docs.add(out.doc_id)
        out.new_docs.add(dest_id)
        out.doc_id = dest_id

    def doc_properties_components_cancel_changes(self):
        self.doc_properties_components_set_active_doc(*self.active_doc)

    @openpaperwork_core.noop
    def doc_properties_components_set_active_docs(self, docs: set):
        pass
