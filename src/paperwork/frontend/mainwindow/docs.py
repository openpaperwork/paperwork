from copy import copy
import datetime
import gettext
import logging
import gc
import time

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk
import PIL

from paperwork_backend.common.doc import BasicDoc
from paperwork_backend.common.page import BasicPage
from paperwork_backend.img.doc import ImgDoc
from paperwork_backend.labels import Label
from paperwork.frontend.labeleditor import LabelEditor
from paperwork.frontend.util import connect_actions
from paperwork.frontend.util.actions import SimpleAction
from paperwork.frontend.util.canvas import Canvas
from paperwork.frontend.util.canvas.animations import SpinnerAnimation
from paperwork.frontend.util.dialog import ask_confirmation
from paperwork.frontend.util.img import add_img_border
from paperwork.frontend.util.img import image2pixbuf
from paperwork.frontend.util.jobs import Job
from paperwork.frontend.util.jobs import JobFactory
from paperwork.frontend.util.renderer import LabelWidget
from paperwork.frontend.widgets import LabelColorButton

_ = gettext.gettext
logger = logging.getLogger(__name__)


def sort_documents_by_date(documents):
    documents.sort()
    documents.reverse()


class JobDocThumbnailer(Job):
    """
    Generate doc list thumbnails
    """

    THUMB_BORDER = 1

    __gsignals__ = {
        'doc-thumbnailing-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'doc-thumbnailing-doc-done': (GObject.SignalFlags.RUN_LAST, None,
                                      (
                                          GObject.TYPE_PYOBJECT,  # thumbnail
                                          GObject.TYPE_PYOBJECT,  # doc
                                          GObject.TYPE_INT,  # current doc
                                          # number of docs being thumbnailed
                                          GObject.TYPE_INT,)),
        'doc-thumbnailing-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = True
    priority = 20

    SMALL_THUMBNAIL_WIDTH = 64
    SMALL_THUMBNAIL_HEIGHT = 80

    def __init__(self, factory, id, doclist, already_loaded):
        Job.__init__(self, factory, id)
        self.doclist = doclist
        self.__already_loaded = already_loaded
        self.__current_idx = -1

    def __resize(self, img):
        (width, height) = img.size
        # always make sure the thumbnail has a specific height
        # otherwise the scrollbar keep moving while loading
        if width > self.SMALL_THUMBNAIL_WIDTH:
            img = img.crop((0, 0, self.SMALL_THUMBNAIL_WIDTH, height))
            img = img.copy()
        elif width < self.SMALL_THUMBNAIL_WIDTH:
            height = min(height, self.SMALL_THUMBNAIL_HEIGHT)
            new_img = PIL.Image.new(
                'RGBA', (self.SMALL_THUMBNAIL_WIDTH, height),
                '#FFFFFF'
            )
            w = int((self.SMALL_THUMBNAIL_WIDTH - width) / 2)
            new_img.paste(img, (w, 0, w + width, height))
            img = new_img
        return img

    def do(self):
        self.can_run = True
        if self.__current_idx >= len(self.doclist):
            return
        if not self.can_run:
            logger.info(
                "Thumbnailing [%s] interrupted (not even started yet)", self
            )
            return

        if self.__current_idx < 0:
            logger.info(
                "Start thumbnailing %d documents (%s)",
                len(self.doclist), self
            )
            self.emit('doc-thumbnailing-start')
            self.__current_idx = 0

        for (idx, doc) in enumerate(self.doclist):
            if doc.docid in self.__already_loaded:
                continue

            if doc.nb_pages <= 0:
                doc.drop_cache()  # even accessing 'nb_pages' may open a file
                continue

            start = time.time()

            # always request the same size, even for small thumbnails
            # so we don't invalidate cache + previous thumbnails
            img = doc.pages[0].get_thumbnail(BasicPage.DEFAULT_THUMB_WIDTH,
                                             BasicPage.DEFAULT_THUMB_HEIGHT)
            doc.drop_cache()
            if not self.can_run:
                logger.info("Thumbnailing [%s] interrupted (0)", self)
                return

            (w, h) = img.size
            factor = max(
                (float(w) / JobDocThumbnailer.SMALL_THUMBNAIL_WIDTH),
                (float(h) / JobDocThumbnailer.SMALL_THUMBNAIL_HEIGHT)
            )
            w /= factor
            h /= factor
            img = img.resize((int(w), int(h)), PIL.Image.ANTIALIAS)
            if not self.can_run:
                logger.info("Thumbnailing [%s] interrupted (1)", self)
                return

            img = self.__resize(img)
            if not self.can_run:
                logger.info("Thumbnailing [%s] interrupted (2)", self)
                return

            img = add_img_border(img, width=self.THUMB_BORDER)
            if not self.can_run:
                logger.info("Thumbnailing [%s] interrupted (3)", self)
                return

            pixbuf = image2pixbuf(img)

            stop = time.time()

            logger.info(
                "[%s]: Got thumbnail for %s (%fs)",
                self, doc.docid, stop - start
            )
            self.emit('doc-thumbnailing-doc-done', pixbuf, doc,
                      idx, len(self.doclist))

            self.__current_idx = idx

        logger.info("End of thumbnailing [%s]", self)
        self.emit('doc-thumbnailing-end')

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()
        if not will_resume and self.__current_idx >= 0:
            self.emit('doc-thumbnailing-end')


GObject.type_register(JobDocThumbnailer)


class JobFactoryDocThumbnailer(JobFactory):
    def __init__(self, doclist):
        JobFactory.__init__(self, "DocThumbnailer")
        self.__doclist = doclist

    def make(self, doclist, already_loaded=()):
        """
        Arguments:
            doclist --- must be an array of (position, document), position
                        being the position of the document
        """
        job = JobDocThumbnailer(
            self, next(self.id_generator), doclist, already_loaded
        )
        job.connect(
            'doc-thumbnailing-start',
            lambda thumbnailer:
            GLib.idle_add(self.__doclist.on_doc_thumbnailing_start_cb,
                          thumbnailer))
        job.connect(
            'doc-thumbnailing-doc-done',
            lambda thumbnailer, thumbnail, doc, doc_nb, total_docs:
            GLib.idle_add(self.__doclist.on_doc_thumbnailing_doc_done_cb,
                          thumbnailer, thumbnail, doc, doc_nb,
                          total_docs))
        job.connect(
            'doc-thumbnailing-end',
            lambda thumbnailer:
            GLib.idle_add(self.__doclist.on_doc_thumbnailing_end_cb,
                          thumbnailer))
        return job


class JobLabelCreator(Job):
    __gsignals__ = {
        'label-creation-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'label-creation-doc-read': (GObject.SignalFlags.RUN_LAST, None,
                                    (GObject.TYPE_FLOAT,
                                     GObject.TYPE_STRING)),
        'label-creation-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 5

    def __init__(self, factory, id, docsearch, new_label, doc):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__new_label = new_label
        self.__doc = doc

    def __progress_cb(self, progression, total, step, doc):
        self.emit('label-creation-doc-read', float(progression) / total,
                  doc.name)

    def do(self):
        self.emit('label-creation-start')
        self._wait(0.5)  # give a little bit of time to Gtk to update
        try:
            self.__docsearch.create_label(self.__new_label, self.__doc,
                                          self.__progress_cb)
        finally:
            self.emit('label-creation-end')


GObject.type_register(JobLabelCreator)


class JobFactoryLabelCreator(JobFactory):
    def __init__(self, doc_list):
        JobFactory.__init__(self, "LabelCreator")
        self.__doc_list = doc_list

    def make(self, docsearch, new_label, doc):
        job = JobLabelCreator(self, next(self.id_generator), docsearch,
                              new_label, doc)
        job.connect('label-creation-start',
                    lambda updater:
                    GLib.idle_add(
                        self.__doc_list.on_label_updating_start_cb,
                        updater))
        job.connect('label-creation-doc-read',
                    lambda updater, progression, doc_name:
                    GLib.idle_add(
                        self.__doc_list.on_label_updating_doc_updated_cb,
                        updater, progression, doc_name))
        job.connect('label-creation-end',
                    lambda updater:
                    GLib.idle_add(
                        self.__doc_list.on_label_updating_end_cb,
                        updater))
        return job


class JobLabelUpdater(Job):
    __gsignals__ = {
        'label-updating-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'label-updating-doc-updated': (GObject.SignalFlags.RUN_LAST, None,
                                       (GObject.TYPE_FLOAT,
                                        GObject.TYPE_STRING)),
        'label-updating-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 5

    def __init__(self, factory, id, docsearch, old_label, new_label):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__old_label = old_label
        self.__new_label = new_label

    def __progress_cb(self, progression, total, step, doc):
        self.emit('label-updating-doc-updated', float(progression) / total,
                  doc.name)

    def do(self):
        self.emit('label-updating-start')
        self._wait(0.5)  # give a little bit of time to Gtk to update
        try:
            self.__docsearch.update_label(self.__old_label, self.__new_label,
                                          self.__progress_cb)
        finally:
            self.emit('label-updating-end')


GObject.type_register(JobLabelUpdater)


class JobFactoryLabelUpdater(JobFactory):
    def __init__(self, doc_list):
        JobFactory.__init__(self, "LabelUpdater")
        self.__doc_list = doc_list

    def make(self, docsearch, old_label, new_label):
        job = JobLabelUpdater(self, next(self.id_generator), docsearch,
                              old_label, new_label)
        job.connect('label-updating-start',
                    lambda updater:
                    GLib.idle_add(
                        self.__doc_list.on_label_updating_start_cb,
                        updater))
        job.connect('label-updating-doc-updated',
                    lambda updater, progression, doc_name:
                    GLib.idle_add(
                        self.__doc_list.on_label_updating_doc_updated_cb,
                        updater, progression, doc_name))
        job.connect('label-updating-end',
                    lambda updater:
                    GLib.idle_add(
                        self.__doc_list.on_label_updating_end_cb,
                        updater))
        return job


class JobLabelDeleter(Job):
    __gsignals__ = {
        'label-deletion-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'label-deletion-doc-updated': (GObject.SignalFlags.RUN_LAST, None,
                                       (GObject.TYPE_FLOAT,
                                        GObject.TYPE_STRING)),
        'label-deletion-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 5

    def __init__(self, factory, id, docsearch, label):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__label = label

    def __progress_cb(self, progression, total, step, doc):
        self.emit('label-deletion-doc-updated', float(progression) / total,
                  doc.name)

    def do(self):
        self.emit('label-deletion-start')
        self._wait(0.5)  # give a little bit of time to Gtk to update
        try:
            self.__docsearch.destroy_label(self.__label, self.__progress_cb)
        finally:
            self.emit('label-deletion-end')


GObject.type_register(JobLabelDeleter)


class JobFactoryLabelDeleter(JobFactory):
    def __init__(self, doc_list):
        JobFactory.__init__(self, "LabelDeleter")
        self.__doc_list = doc_list

    def make(self, docsearch, label):
        job = JobLabelDeleter(self, next(self.id_generator), docsearch, label)
        job.connect('label-deletion-start',
                    lambda deleter:
                    GLib.idle_add(self.__doc_list.on_label_updating_start_cb,
                                  deleter))
        job.connect('label-deletion-doc-updated',
                    lambda deleter, progression, doc_name:
                    GLib.idle_add(
                        self.__doc_list.on_label_deletion_doc_updated_cb,
                        deleter, progression, doc_name))
        job.connect('label-deletion-end',
                    lambda deleter:
                    GLib.idle_add(self.__doc_list.on_label_updating_end_cb,
                                  deleter))
        return job


class ActionOpenSelectedDocument(SimpleAction):
    """
    Starts a new document.
    """
    def __init__(self, main_window, config, doclist):
        SimpleAction.__init__(self, "Open selected document")
        self.__main_win = main_window
        self.__config = config
        self.__doclist = doclist

    def do(self):
        self.on_row_activated_cb(self)

    def on_row_activated_cb(self, _=None, row=None):
        if not self.__doclist.enabled:
            return

        SimpleAction.do(self)

        doclist = self.__doclist.gui['list']
        if row is None:
            row = doclist.get_selected_row()
        if row is None:
            return
        docid = self.__doclist.model['by_row'][row]
        doc = self.__main_win.docsearch.get_doc_from_docid(docid, inst=False)
        if doc is None:
            # assume new doc
            doc = self.__doclist.get_new_doc()

        logger.info("Showing doc %s" % doc)
        if doc.nb_pages <= 1:
            self.__main_win.set_layout('paged', force_refresh=False)
        else:
            self.__main_win.set_layout('grid', force_refresh=False)
        self.__main_win.show_doc(doc)


class ActionSwitchToDocList(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Switch back to doc list")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.doc_properties_panel.apply_properties()
        self.__main_win.switch_leftpane("doc_list")


class ActionParseDocDate(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Set document date")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        date_entry = self.__main_win.doc_properties_panel.widgets['name']
        date_txt = date_entry.get_text()

        # make sure the format is standardized
        valid = True
        try:
            date = BasicDoc.parse_name(date_txt)
            logger.info("Valid date: {}".format(date_txt))
            css = "GtkEntry { color: black; background: #70CC70; }"
        except ValueError:
            logger.info("Invalid date: {}".format(date_txt))
            valid = False
            css = "GtkEntry { color: black; background: #CC3030; }"

        if valid and date == self.__main_win.doc_properties_panel.doc.date:
            css = "GtkEntry { color: black; background: #CCCCCC; }"

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        css_context = date_entry.get_style_context()
        css_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        if not valid:
            return

        self.__main_win.doc_properties_panel._set_calendar(date)
        if self.__main_win.doc_properties_panel.doc.date != date:
            self.__main_win.doc_properties_panel.new_doc_date = date
        else:
            self.__main_win.doc_properties_panel.new_doc_date = None


class ActionSetDocDateFromCalendar(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Set document date")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        calendar = self.__main_win.doc_properties_panel.widgets['calendar']
        popover = self.__main_win.doc_properties_panel.popovers['calendar']
        date = calendar.get_date()
        date = datetime.datetime(year=date[0], month=date[1] + 1, day=date[2])
        date_txt = BasicDoc.get_name(date)

        entry = self.__main_win.doc_properties_panel.widgets['name']
        entry.set_text(date_txt)

        if self.__main_win.doc_properties_panel.doc.date != date:
            self.__main_win.doc_properties_panel.new_doc_date = date
        else:
            self.__main_win.doc_properties_panel.new_doc_date = None

        popover.set_visible(False)


class ActionCreateLabel(SimpleAction):
    def __init__(self, main_window, doc_properties):
        SimpleAction.__init__(self, "Creating label")
        self.__main_win = main_window
        self.__doc_properties = doc_properties

    def do(self):
        SimpleAction.do(self)
        labeleditor = LabelEditor()
        if labeleditor.edit(self.__main_win.window) == "ok":
            logger.info("Adding label %s to doc %s"
                        % (labeleditor.label.name, self.__main_win.doc))
            job = self.__doc_properties.job_factories['label_creator'].make(
                self.__main_win.docsearch, labeleditor.label,
                self.__main_win.doc)
            self.__main_win.schedulers['main'].schedule(job)
            self.__doc_properties.refresh_label_list()


class ActionEditLabel(SimpleAction):
    """
    Edit the selected label.
    """
    def __init__(self, main_window, doc_properties):
        SimpleAction.__init__(self, "Editing label")
        self.__main_win = main_window
        self.__doc_properties = doc_properties

    def do(self):
        SimpleAction.do(self)

        # Open the russian dolls to retrieve the selected label.
        label_list = self.__doc_properties.lists['labels']['gui']
        selected_row = label_list.get_selected_row()
        if selected_row is None:
            logger.warning("No label selected")
            return True
        label_box = selected_row.get_children()[0]
        label_name = label_box.get_children()[2].get_text()
        label_color = label_box.get_children()[1].get_rgba().to_string()
        label = Label(label_name, label_color)

        new_label = copy(label)
        editor = LabelEditor(new_label)
        reply = editor.edit(self.__main_win.window)
        if reply != "ok":
            logger.warning("Label edition cancelled")
            return
        logger.info("Label edited. Applying changes")
        job = self.__doc_properties.job_factories['label_updater'].make(
            self.__main_win.docsearch, label, new_label)
        self.__main_win.schedulers['main'].schedule(job)
        self.__doc_properties.refresh_label_list()


class ActionDeleteLabel(SimpleAction):
    """
    Delete the selected label.
    """
    def __init__(self, main_window, doc_properties):
        SimpleAction.__init__(self, "Deleting label")
        self.__main_win = main_window
        self.__doc_properties = doc_properties
        self._label = None

    def do(self):
        SimpleAction.do(self)

        # Open the russian dolls to retrieve the selected label.
        label_list = self.__doc_properties.lists['labels']['gui']
        selected_row = label_list.get_selected_row()
        if selected_row is None:
            logger.warning("No label selected")
            return True
        label_box = selected_row.get_children()[0]
        label_name = label_box.get_children()[2].get_text()
        label_color = label_box.get_children()[1].get_rgba().to_string()
        self._label = Label(label_name, label_color)

        if not ask_confirmation(self.__main_win.window, self._do_delete):
            return

    def _do_delete(self):
        logger.info("Label {} must be deleted. Applying changes".format(
            self._label
        ))
        job = self.__doc_properties.job_factories['label_deleter'].make(
            self.__main_win.docsearch, self._label
        )
        self.__main_win.schedulers['main'].schedule(job)
        self.__doc_properties.refresh_label_list()


class ActionDeleteDoc(SimpleAction):
    def __init__(self, main_window, doc=None):
        SimpleAction.__init__(self, "Delete document")
        self.__main_win = main_window
        self.__doc = doc

    def do(self):
        """
        Ask for confirmation and then delete the document being viewed.
        """
        super().do()
        ask_confirmation(self.__main_win.window, self._do)

    def _do(self):
        SimpleAction.do(self)
        if self.__doc is None:
            doc = self.__main_win.doc
        else:
            doc = self.__doc

        self.__main_win.actions['new_doc'][1].do()

        logger.info("Deleting ...")
        job = self.__main_win.job_factories['index_updater'].make(
            self.__main_win.docsearch,
            del_docs={doc},
            optimize=False,
            reload_list=True
        )
        job.connect(
            "index-update-end",
            lambda job: GLib.idle_add(
                self._on_doc_deleted_from_index, doc
            )
        )
        self.__main_win.new_doc()
        self.__main_win.schedulers['main'].schedule(job)

    def _on_doc_deleted_from_index(self, doc):
        doc.destroy()
        self.__main_win.refresh_doc_list()


class DocList(object):
    LIST_CHUNK = 50

    def __init__(self, main_win, config, widget_tree):
        self.__main_win = main_win
        self.__config = config
        self.enabled = True

        self.default_thumbnail = self.__init_default_thumbnail(
            JobDocThumbnailer.SMALL_THUMBNAIL_WIDTH,
            JobDocThumbnailer.SMALL_THUMBNAIL_HEIGHT)

        self.gui = {
            'list': widget_tree.get_object("listboxDocList"),
            'box': widget_tree.get_object("doclist_box"),
            'scrollbars': widget_tree.get_object("scrolledwindowDocList"),
            'last_scrollbar_value': -1,
            'spinner': SpinnerAnimation((0, 0)),
            'nb_boxes': 0,
        }
        self.gui['loading'] = Canvas(self.gui['scrollbars'])
        self.gui['loading'].set_visible(False)
        self.gui['box'].add(self.gui['loading'])
        self.gui['scrollbars'].connect(
            "size-allocate",
            lambda x, s: GLib.idle_add(self._on_size_allocate)
        )

        self.actions = {
            'open_doc': (
                [
                    self.gui['list'],
                ],
                ActionOpenSelectedDocument(main_win, config, self)
            ),
        }
        connect_actions(self.actions)

        self.model = {
            'has_new': False,
            'docids': [],
            'by_row': {},  # Gtk.ListBoxRow: docid
            'by_id': {},  # docid: Gtk.ListBoxRow
            # keep the thumbnails in cache
            'thumbnails': {}  # docid: pixbuf
        }
        self.new_doc = ImgDoc(config['workdir'].value)

        self.job_factories = {
            'doc_thumbnailer': JobFactoryDocThumbnailer(self),
        }
        self.selected_doc = None

        self.gui['scrollbars'].get_vadjustment().connect(
            "value-changed",
            lambda v: GLib.idle_add(self._on_scrollbar_value_changed)
        )

        self.gui['list'].add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        self.gui['list'].connect("button-press-event", self._on_button_pressed)

        self.gui['list'].connect(
            "size-allocate",
            lambda w, s: GLib.idle_add(self._on_scrollbar_value_changed)
        )

        self.gui['list'].connect("drag-motion", self._on_drag_motion)
        self.gui['list'].connect("drag-leave", self._on_drag_leave)
        self.gui['list'].connect(
            "drag-data-received",
            self._on_drag_data_received
        )
        self.gui['list'].drag_dest_set(
            Gtk.DestDefaults.ALL,
            [], Gdk.DragAction.MOVE
        )
        self.gui['list'].drag_dest_add_text_targets()

        self.accel_group = Gtk.AccelGroup()
        self.__main_win.window.add_accel_group(self.accel_group)

        self.show_loading()

    def __init_default_thumbnail(self, width=BasicPage.DEFAULT_THUMB_WIDTH,
                                 height=BasicPage.DEFAULT_THUMB_HEIGHT):
        img = PIL.Image.new("RGB", (
            width,
            height,
        ), color="#EEEEEE")
        img = add_img_border(img, 1)
        return image2pixbuf(img)

    def _on_button_pressed(self, widget, event):
        self.__main_win.allow_multiselect = bool(
            event.state & Gdk.ModifierType.CONTROL_MASK or
            event.state & Gdk.ModifierType.SHIFT_MASK
        )

    def _on_scrollbar_value_changed(self):
        vadjustment = self.gui['scrollbars'].get_vadjustment()
        if vadjustment.get_value() == self.gui['last_scrollbar_value']:
            # avoid repeated requests due to adding documents to the
            # GtkListBox (even if frozen ...)
            return
        self.gui['last_scrollbar_value'] = vadjustment.get_value()
        self.__main_win.schedulers['main'].cancel_all(
            self.job_factories['doc_thumbnailer']
        )

        # because we use GLib.idle_add() before calling this function
        # the scrollbar may have disappear (--> application close)
        # before we are called
        if vadjustment is None:
            return

        # XXX(Jflesch): assumptions: values are in px
        value = vadjustment.get_value()
        lower = vadjustment.get_lower()
        upper = vadjustment.get_upper()
        page_size = vadjustment.get_page_size()

        # if we are in the lower part (10%), add the next chunk of boxes
        u = upper - lower
        v = value - lower + page_size
        if lower + page_size < upper and v >= u:
            self._add_boxes()

        start_y = value
        end_y = value + page_size

        start_row = self.gui['list'].get_row_at_y(start_y)
        end_row = self.gui['list'].get_row_at_y(end_y)

        start_idx = 0
        if start_row:
            start_idx = start_row.get_index()
        end_idx = len(self.gui['list'])
        if end_row:
            end_idx = end_row.get_index()
        if start_row == end_row:
            return
        if end_idx < start_idx:
            logger.warn("Thumbnailing: End_idx (%d) < start_idx (%d) !?"
                        % (end_idx, start_idx))
            end_idx = 99999999

        documents = []
        for row_idx in range(start_idx, end_idx + 1):
            row = self.gui['list'].get_row_at_index(row_idx)
            if row is None:
                break
            docid = self.model['by_row'][row]
            if docid in self.model['thumbnails']:
                # already loaded
                continue
            doc = self.__main_win.docsearch.get_doc_from_docid(
                docid, inst=False
            )
            if doc:
                documents.append(doc)

        if len(documents) > 0:
            logger.info("Will get thumbnails for %d documents [%d-%d]"
                        % (len(documents), start_idx, end_idx))
            job = self.job_factories['doc_thumbnailer'].make(
                documents, self.model['thumbnails']
            )
            self.__main_win.schedulers['main'].schedule(job)

    def scroll_to(self, row):
        adj = row.get_allocation().y
        adj -= (self.gui['scrollbars'].get_vadjustment().get_page_size() / 2)
        adj += (row.get_allocation().height / 2)
        min_val = self.gui['scrollbars'].get_vadjustment().get_lower()
        if adj < min_val:
            adj = min_val
        self.gui['scrollbars'].get_vadjustment().set_value(adj)

    def _on_drag_motion(self, canvas, drag_context, x, y, time):
        target_row = self.gui['list'].get_row_at_y(y)
        if not target_row or target_row not in self.model['by_row']:
            self._on_drag_leave(canvas, drag_context, time)
            return False

        target_docid = self.model['by_row'][target_row]
        try:
            target_doc = self.__main_win.docsearch.get(target_docid)
        except KeyError:
            target_doc = self.get_new_doc()

        if not target_doc.can_edit:
            self._on_drag_leave(canvas, drag_context, time)
            return False

        Gdk.drag_status(drag_context, Gdk.DragAction.MOVE, time)

        self.gui['list'].drag_unhighlight_row()
        self.gui['list'].drag_highlight_row(target_row)
        return True

    def _on_drag_leave(self, canvas, drag_context, time):
        self.gui['list'].drag_unhighlight_row()

    def _on_drag_data_received(self, widget, drag_context,
                               x, y, data, info, time):
        page_id = data.get_text()

        target_row = self.gui['list'].get_row_at_y(y)
        if not target_row or target_row not in self.model['by_row']:
            logger.warn("Drag-n-drop: Invalid doc row ?!")
            drag_context.finish(False, False, time)  # success = False
            return

        target_docid = self.model['by_row'][target_row]
        logger.info("Drag-n-drop data received on doc list: [%s] --> [%s]"
                    % (page_id, target_docid))

        src_page = self.__main_win.docsearch.get(page_id)
        try:
            target_doc = self.__main_win.docsearch.get(target_docid)
        except KeyError:
            target_doc = self.get_new_doc()
        is_new = target_doc.is_new

        if not src_page.doc.can_edit:
            logger.warn("Drag-n-drop: Cannot modify source document")
            drag_context.finish(False, False, time)  # success = False
            return
        if not target_doc.can_edit:
            logger.warn("Drag-n-drop: Cannot modify destination document")
            drag_context.finish(False, False, time)  # success = False
            return
        if src_page.doc.docid == target_doc.docid:
            logger.warn("Drag-n-drop: Source and destionation document"
                        " are the same")
            drag_context.finish(False, False, time)  # success = False
            return

        target_doc.add_page(src_page.img, src_page.boxes)
        src_page.destroy()
        src_page.doc.drop_cache()
        if src_page.doc.nb_pages <= 0:
            src_page.doc.destroy()
        drag_context.finish(True, True, time)  # success = True

        if not is_new:
            GLib.idle_add(self.__on_drag_reload, src_page,
                          {target_doc, src_page.doc}, set())
        else:
            GLib.idle_add(self.__on_drag_reload, src_page,
                          {src_page.doc}, {target_doc})

    def __on_drag_reload(self, src_page, upd_docs, new_docs):
        # Will force a redisplay of all the pages, but without
        # the one we destroyed. Will also force a scrolling to
        # where was the one we destroyed
        self.__main_win.show_page(src_page, force_refresh=True)
        self.show_loading()
        if new_docs:
            self.__main_win.upd_index(new_docs, new=True)
        assert(upd_docs)
        self.__main_win.upd_index(upd_docs, new=False)

    def get_new_doc(self):
        if self.new_doc.is_new:
            return self.new_doc
        self.new_doc = ImgDoc(self.__config['workdir'].value)
        return self.new_doc

    def insert_new_doc(self):
        # append a new document to the list
        doc = self.get_new_doc()
        self.model['has_new'] = True
        rowbox = Gtk.ListBoxRow()
        self._make_listboxrow_doc_widget(doc, rowbox, False)
        self.model['by_row'][rowbox] = doc.docid
        self.model['by_id'][doc.docid] = rowbox
        self.gui['list'].insert(rowbox, 0)
        if self.__main_win.doc.is_new:
            self.gui['list'].select_row(rowbox)
        return doc

    def open_new_doc(self):
        if not self.model['has_new']:
            self.insert_new_doc()
        self.gui['list'].unselect_all()
        doc = self.get_new_doc()
        self.__main_win.show_doc(doc)

    def clear(self):
        self.gui['list'].freeze_child_notify()
        try:
            while True:
                row = self.gui['list'].get_row_at_index(0)
                if row is None:
                    break
                self.gui['list'].remove(row)

            self.model['by_row'] = {}
            self.model['by_id'] = {}
            self.model['has_new'] = False
            self.gui['nb_boxes'] = 0
        finally:
            self.gui['list'].thaw_child_notify()

    def _make_listboxrow_doc_widget(self, doc, rowbox, selected=False):
        globalbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 10)

        # thumbnail
        if doc.docid in self.model['thumbnails']:
            thumbnail = self.model['thumbnails'][doc.docid]
            thumbnail = Gtk.Image.new_from_pixbuf(thumbnail)
        else:
            thumbnail = Gtk.Image.new_from_pixbuf(self.default_thumbnail)
            thumbnail.set_size_request(JobDocThumbnailer.SMALL_THUMBNAIL_WIDTH,
                                       JobDocThumbnailer.SMALL_THUMBNAIL_HEIGHT)

        globalbox.add(thumbnail)

        internalbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 3)
        globalbox.add(internalbox)

        # doc name
        docname = Gtk.Label.new(doc.name)
        docname.set_justify(Gtk.Justification.LEFT)
        docname.set_halign(Gtk.Align.START)
        internalbox.add(docname)

        # doc labels
        labels = LabelWidget(doc.labels)
        labels.set_size_request(170, 10)
        internalbox.add(labels)

        # buttons
        button_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
        button_box.set_size_request(20, 40)
        button_box.set_homogeneous(True)
        globalbox.pack_start(button_box, False, True, 0)

        edit_button = Gtk.Button.new_from_icon_name(
            "document-properties-symbolic",
            Gtk.IconSize.MENU)
        edit_button.set_relief(Gtk.ReliefStyle.NONE)
        edit_button.connect(
            "clicked",
            lambda _: GLib.idle_add(
                self.__main_win.switch_leftpane, 'doc_properties'))

        # shortcut
        (key, mod) = Gtk.accelerator_parse('<Primary>e')
        edit_button.add_accelerator('clicked', self.accel_group, key, mod,
                                    Gtk.AccelFlags.VISIBLE)

        button_box.add(edit_button)

        delete_button = Gtk.Button.new_from_icon_name(
            "edit-delete-symbolic",
            Gtk.IconSize.MENU)
        delete_button.set_relief(Gtk.ReliefStyle.NONE)
        delete_button.connect(
            "clicked",
            lambda _: GLib.idle_add(
                ActionDeleteDoc(self.__main_win, doc).do))

        button_box.add(delete_button)

        for child in rowbox.get_children():
            rowbox.remove(child)
        rowbox.add(globalbox)
        rowbox.show_all()
        if not selected:
            delete_button.set_visible(False)
            edit_button.set_visible(False)

    def _show_loading(self):
        # remove the list, put the canvas+spinner instead
        self.gui['loading'].remove_all_drawers()
        self.gui['loading'].add_drawer(self.gui['spinner'])
        self.gui['list'].set_visible(False)
        self.gui['loading'].set_visible(True)
        self._on_size_allocate()

    def show_loading(self):
        GLib.idle_add(self._show_loading)

    def _add_boxes(self):
        start = self.gui['nb_boxes']
        stop = self.gui['nb_boxes'] + self.LIST_CHUNK
        docs = self.model['docids'][start:stop]

        logger.info("Will display documents {}:{} (actual number: {})".format(
            start, stop, len(docs)
        ))

        for docid in docs:
            rowbox = self.model['by_id'][docid]
            self.gui['list'].add(rowbox)
            self.gui['nb_boxes'] += 1

    def set_docs(self, documents, need_new_doc=True):
        self.__main_win.schedulers['main'].cancel_all(
            self.job_factories['doc_thumbnailer']
        )

        self.clear()
        GLib.idle_add(self._set_docs, documents, need_new_doc)

    def _set_docs(self, documents, need_new_doc):
        self.model['docids'] = [doc.docid for doc in documents]
        for doc in documents:
            rowbox = Gtk.ListBoxRow()
            selected = (doc.docid == self.__main_win.doc.docid)
            self._make_listboxrow_doc_widget(doc, rowbox, selected)
            self.model['by_row'][rowbox] = doc.docid
            self.model['by_id'][doc.docid] = rowbox

        self.gui['list'].freeze_child_notify()
        try:
            self._add_boxes()
            if need_new_doc:
                self.insert_new_doc()

            self.gui['list'].set_visible(True)
        finally:
            self.gui['list'].thaw_child_notify()

        if (self.__main_win.doc and
                self.__main_win.doc.docid in self.model['by_id']):
            self.make_doc_box_visible(self.__main_win.doc)
            row = self.model['by_id'][self.__main_win.doc.docid]
            self.gui['list'].select_row(row)
            GLib.idle_add(self.scroll_to, row)

        # remove the spinner, put the list instead
        self.gui['loading'].remove_all_drawers()
        self.gui['loading'].set_visible(False)

        self.gui['last_scrollbar_value'] = -1  # force refresh of thumbnails
        GLib.idle_add(self._on_scrollbar_value_changed)

    def refresh_docs(self, docs, redo_thumbnails=True):
        """
        Refresh specific documents in the document list

        Arguments:
            docs --- Array of Doc
        """
        for doc in docs:
            if doc.docid in self.model['by_id']:
                rowbox = self.model['by_id'][doc.docid]
                self._make_listboxrow_doc_widget(
                    doc, rowbox,
                    doc.docid == self.__main_win.doc.docid
                )
            else:
                # refresh the whole list for now, it's much simpler
                self.refresh()
                return

        # and rethumbnail what must be
        if redo_thumbnails:
            for doc in docs:
                if doc.docid in self.model['thumbnails']:
                    self.model['thumbnails'].pop(doc.docid)
        docs = [x for x in docs]
        logger.info("Will redo thumbnails: %s" % str(docs))
        job = self.job_factories['doc_thumbnailer'].make(docs)
        self.__main_win.schedulers['main'].schedule(job)

    def refresh(self):
        """
        Update the suggestions list and the matching documents list based on
        the keywords typed by the user in the search field.
        Warning: Will reset all the thumbnail to the default one
        """
        GLib.idle_add(self._refresh)

    def _refresh(self):
        self.__main_win.schedulers['search'].cancel_all(
            self.__main_win.job_factories['doc_searcher']
        )
        search = self.__main_win.search_field.get_text()
        self.show_loading()
        job = self.__main_win.job_factories['doc_searcher'].make(
            docsearch=self.__main_win.docsearch,
            sort_func=self.__main_win.get_doc_sorting()[1],
            search_type='fuzzy',
            search=search)
        self.__main_win.schedulers['search'].schedule(job)

    def has_multiselect(self):
        return (len(self.gui['list'].get_selected_rows()) > 1)

    def unselect_doc(self, doc):
        if doc.docid not in self.model['by_id']:
            return
        row = self.model['by_id'][doc.docid]
        self.gui['list'].unselect_row(row)

    def get_closest_selected_doc(self, doc):
        current = self.model['by_id'][doc.docid].get_index()
        best_row = None
        best_distance = 9999999999
        for row in self.gui['list'].get_selected_rows():
            distance = abs(row.get_index() - current)
            assert distance > 0, "'doc' should have been unselected first"
            if distance < best_distance:
                best_distance = distance
                best_row = row
        if not best_row:
            return
        docid = self.model['by_row'][best_row]
        return self.__main_win.docsearch.get_doc_from_docid(docid, inst=False)

    def make_doc_box_visible(self, doc):
        if doc.docid not in self.model['docids']:
            return
        doc_pos = self.model['docids'].index(doc.docid)
        logger.info(
            "Document position: {}"
            " | Number of boxes currently displayed: {}".format(
                doc_pos, self.gui['nb_boxes']
            )
        )
        if doc_pos < self.gui['nb_boxes']:
            return
        self.gui['list'].freeze_child_notify()
        try:
            while doc_pos >= self.gui['nb_boxes']:
                self._add_boxes()
        finally:
            self.gui['list'].thaw_child_notify()

    def select_doc(self, doc=None, offset=None, open_doc=True):
        self.enabled = open_doc
        try:
            if doc:
                self.make_doc_box_visible(doc)

            assert(doc is not None or offset is not None)
            if doc is not None:
                if doc.docid not in self.model['by_id']:
                    logger.warning(
                        "Cannot select document {}. Not found !".format(
                            doc.docid
                        )
                    )
                    return
                row = self.model['by_id'][doc.docid]
            else:
                row = self.gui['list'].get_selected_row()
            if row is None:
                logger.warning("Unable to get doc row")
                return
            self.gui['list'].unselect_all()
            if offset is not None:
                row_index = row.get_index()
                row_index += offset
                row = self.gui['list'].get_row_at_index(row_index)
                if not row:
                    return
                docid = self.model['by_row'][row]
                doc = self.__main_win.docsearch.get_doc_from_docid(
                    docid, inst=True
                )
            self.gui['list'].unselect_all()
            self.gui['list'].select_row(row)
            if open_doc and doc:
                self.__main_win.show_doc(doc)
            return row
        finally:
            self.enabled = True

    def _on_size_allocate(self):
        visible = self.gui['scrollbars'].get_allocation()
        visible = (visible.width, visible.height)
        self.gui['spinner'].position = (
            (visible[0] - SpinnerAnimation.ICON_SIZE) / 2,
            (visible[1] - SpinnerAnimation.ICON_SIZE) / 2
        )

    def on_doc_thumbnailing_start_cb(self, src):
        self.__main_win.set_progression(src, 0.0, _("Loading thumbnails ..."))
        self.gui['list'].freeze_child_notify()

    def on_doc_thumbnailing_doc_done_cb(self, src, thumbnail,
                                        doc, doc_nb, total_docs):
        self.__main_win.set_progression(
            src, (float(doc_nb + 1) / total_docs),
            _("Loading thumbnails ...")
        )
        self.model['thumbnails'][doc.docid] = thumbnail
        row = self.model['by_id'][doc.docid]
        box = row.get_children()[0]
        thumbnail_widget = box.get_children()[0]
        thumbnail_widget.set_from_pixbuf(thumbnail)

    def on_doc_thumbnailing_end_cb(self, src):
        self.__main_win.set_progression(src, 0.0, None)
        self.gui['list'].thaw_child_notify()
        gc.collect()

    def __set_doc_buttons_visible(self, doc, visible):
        if (doc is None or
                doc.docid not in self.model['by_id'] or
                doc.is_new):
            return

        row = self.model['by_id'][doc.docid]
        to_examine = row.get_children()
        while len(to_examine) > 0:
            widget = to_examine.pop()
            if type(widget) is Gtk.Button:
                widget.set_visible(visible)
            if hasattr(widget, 'get_children'):
                to_examine += widget.get_children()

    def set_selected_doc(self, doc):
        if self.selected_doc:
            self.__set_doc_buttons_visible(self.selected_doc, False)
        self.selected_doc = doc
        if self.selected_doc:
            self.__set_doc_buttons_visible(self.selected_doc, True)

    def get_selected_docs(self):
        rows = self.gui['list'].get_selected_rows()
        docids = [self.model['by_row'][row] for row in rows]
        return [
            self.__main_win.docsearch.get_doc_from_docid(docid, inst=True)
            for docid in docids
        ]


class DocPropertiesPanel(object):
    def __init__(self, main_window, widget_tree):
        self.__main_win = main_window
        self.widgets = {
            'ok': widget_tree.get_object("toolbuttonValidateDocProperties"),
            'name': widget_tree.get_object("docname_entry"),
            'labels': widget_tree.get_object("listboxLabels"),
            'row_add_label': widget_tree.get_object("rowAddLabel"),
            'button_add_label': widget_tree.get_object("buttonAddLabel"),
            'extra_keywords': widget_tree.get_object("extrakeywords_textview"),
            'extra_keywords_default_buffer':
                widget_tree.get_object("extrakeywords_default_textbuffer"),
            'calendar': widget_tree.get_object("calendar_calendar"),
        }
        self.doc = self.__main_win.doc
        self.new_doc_date = None
        self.actions = {
            'apply_doc_edit': (
                [
                    self.widgets['ok']
                ],
                ActionSwitchToDocList(self.__main_win),
            ),
            'parse_doc_date': (
                [
                    self.widgets['name'],
                ],
                ActionParseDocDate(self.__main_win),
            ),
            'set_day': (
                [
                    self.widgets['calendar']
                ],
                ActionSetDocDateFromCalendar(self.__main_win),
            ),
            'create_label': (
                [
                    self.widgets['button_add_label']
                ],
                ActionCreateLabel(self.__main_win, self),
            ),
        }
        connect_actions(self.actions)

        self.widgets['name'].connect(
            "icon-release", lambda entry, icon, event:
            GLib.idle_add(self._open_calendar))

        self.job_factories = {
            'label_creator': JobFactoryLabelCreator(self),
            'label_deleter': JobFactoryLabelDeleter(self),
            'label_updater': JobFactoryLabelUpdater(self),
        }

        self.lists = {
            'labels': {
                'gui': widget_tree.get_object("listboxLabels")
            },
        }

        self.popovers = {
            "calendar": widget_tree.get_object("calendar_popover")
        }

        labels = sorted(main_window.docsearch.label_list)
        self.labels = {label: (None, None) for label in labels}

        default_buf = self.widgets['extra_keywords_default_buffer']
        self.default_extra_text = self.get_text_from_buffer(default_buf)
        self.widgets['extra_keywords'].connect("focus-in-event",
                                               self.on_keywords_focus_in)
        self.widgets['extra_keywords'].connect("focus-out-event",
                                               self.on_keywords_focus_out)

    def get_text_from_buffer(self, text_buffer):
        start = text_buffer.get_iter_at_offset(0)
        end = text_buffer.get_iter_at_offset(-1)
        return text_buffer.get_text(start, end, False)

    def set_doc(self, doc):
        self.doc = doc
        self.reload_properties()

    def reload_properties(self):
        self.widgets['name'].set_text(self.doc.name)
        self.refresh_label_list()
        self.refresh_keywords_textview()

    def _set_calendar(self, date):
        self.widgets['calendar'].select_month(date.month - 1, date.year)
        self.widgets['calendar'].select_day(date.day)

    def _open_calendar(self):
        self.popovers['calendar'].set_relative_to(
            self.widgets['name'])
        if self.new_doc_date is not None:
            self._set_calendar(self.new_doc_date)
        else:
            try:
                date = self.doc.date
                self.widgets['calendar'].select_month(date.month - 1, date.year)
                self.widgets['calendar'].select_day(date.day)
            except Exception as exc:
                logger.warning("Failed to parse document date: %s --> %s"
                               % (str(self.doc.docid), str(exc)))
        self.popovers['calendar'].set_visible(True)

    def apply_properties(self):
        has_changed = False

        date_txt = self.widgets['name'].get_text()
        try:
            date = BasicDoc.parse_name(date_txt)
        except ValueError:
            logger.warning("Invalid date format: {}".format(date_txt))
            msg = _("Invalid date format: {}").format(date_txt)
            dialog = Gtk.MessageDialog(
                parent=self.__main_win.window,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=msg
            )
            dialog.connect("response", lambda dialog, response:
                           GLib.idle_add(dialog.destroy))
            dialog.show_all()
            raise

        # Labels
        logger.info("Checking for new labels")
        doc_labels = sorted(self.doc.labels)
        new_labels = []
        for (label, (row, check_button, edit_button, delete_button)) \
                in self.labels.items():
            if check_button.get_active():
                new_labels.append(label)
        new_labels.sort()
        if doc_labels != new_labels:
            logger.info("Apply new labels")
            self.doc.labels = new_labels
            has_changed = True

        # Keywords
        logger.info("Checking for new keywords")
        # text currently set
        current_extra_text = self.doc.extra_text
        # text actually typed in
        buf = self.widgets['extra_keywords'].get_buffer()
        new_extra_text = self.get_text_from_buffer(buf)
        if (new_extra_text != current_extra_text) and (
                new_extra_text != self.default_extra_text):
            logger.info("Apply new keywords")
            self.doc.extra_text = new_extra_text
            has_changed = True

        # Date
        if self.doc.date == date:
            if has_changed:
                self.__main_win.upd_index({self.doc})
        else:
            old_doc = self.doc.clone()
            # this case is more tricky --> del + new
            job = self.__main_win.job_factories['index_updater'].make(
                self.__main_win.docsearch,
                del_docs={old_doc},
                optimize=False,
                reload_list=False
            )
            new_doc_date = self.new_doc_date
            job.connect(
                "index-update-end", lambda job:
                GLib.idle_add(self.__rename_doc, old_doc, new_doc_date)
            )
            self.new_doc_date = None
            self.__main_win.schedulers['main'].schedule(job)

        self.__main_win.refresh_header_bar()

    def __rename_doc(self, old_doc, new_doc_date):
        old_doc.date = new_doc_date
        old_doc.drop_cache()
        job = self.__main_win.job_factories['index_updater'].make(
            self.__main_win.docsearch,
            new_docs={old_doc},
            optimize=False,
            reload_list=True
        )
        self.__main_win.schedulers['main'].schedule(job)
        self.__main_win.show_doc(old_doc, force_refresh=True)

    def _clear_label_list(self):
        self.widgets['labels'].freeze_child_notify()
        try:
            while True:
                row = self.widgets['labels'].get_row_at_index(0)
                if row is None:
                    break
                self.widgets['labels'].remove(row)
        finally:
            self.labels = {}
            self.widgets['labels'].thaw_child_notify()

    def _readd_label_widgets(self, labels):
        label_widgets = {}
        self.widgets['labels'].freeze_child_notify()
        try:
            # Add a row for each label
            for label in labels:
                label_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 10)

                # Custom check_button with unvisible checkbox
                empty_image = Gtk.Image()
                check_button = Gtk.ToggleButton()
                check_button.set_image(empty_image)
                check_button.set_always_show_image(True)
                check_button.set_relief(Gtk.ReliefStyle.NONE)
                check_style = check_button.get_style_context()
                check_style.remove_class("button")
                check_button.connect("clicked", self.on_check_button_clicked)
                label_box.add(check_button)

                # Custom color_button wich opens custom dialog
                edit_button = LabelColorButton()
                edit_button.set_rgba(label.color)
                edit_button.set_relief(Gtk.ReliefStyle.NONE)
                edit_button.connect("clicked", self.on_label_button_clicked)
                ActionEditLabel(self.__main_win, self).connect([edit_button])
                label_box.add(edit_button)

                label_widget = Gtk.Label.new(label.name)
                label_widget.set_halign(Gtk.Align.START)
                label_box.add(label_widget)
                label_box.child_set_property(label_widget, 'expand', True)

                delete_button = Gtk.Button.new_from_icon_name(
                    "edit-delete", Gtk.IconSize.MENU
                )
                delete_button.set_relief(Gtk.ReliefStyle.NONE)
                delete_button.connect("clicked", self.on_label_button_clicked)
                ActionDeleteLabel(self.__main_win, self).connect(
                    [delete_button]
                )
                label_box.add(delete_button)

                rowbox = Gtk.ListBoxRow()
                rowbox.add(label_box)
                rowbox.set_property('height_request', 30)
                rowbox.show_all()
                delete_button.set_visible(False)
                self.widgets['labels'].add(rowbox)

                label_widgets[label] = (
                    rowbox, check_button, edit_button, delete_button
                )

            # The last row allows to add new labels
            self.widgets['labels'].add(self.widgets['row_add_label'])
        finally:
            self.labels = label_widgets
            self.widgets['labels'].connect(
                "row-activated", self.on_row_activated)
            self.widgets['labels'].thaw_child_notify()

    def on_check_button_clicked(self, check_button):
        """
        Toggle the image displayed into the check_button
        """
        if check_button.get_active():
            checkmark = Gtk.Image.new_from_icon_name("object-select-symbolic",
                                                     Gtk.IconSize.MENU)
            check_button.set_image(checkmark)
        else:
            empty_image = Gtk.Image()
            check_button.set_image(empty_image)

    def on_label_button_clicked(self, button):
        """
        Find the row the button belongs to, and select it.
        """
        label_box = button.get_parent()
        row = label_box.get_parent()
        label_list = self.lists['labels']['gui']
        label_list.select_row(row)

    def on_row_activated(self, rowbox, row):
        """
        When no specific part of a row is clicked on, do as if user had clicked
        on it's check_button. This requires less precision for the user.
        """
        selected_row = rowbox.get_selected_row()

        for (label, (row, check_button, edit_button, delete_button)) \
                in self.labels.items():
            delete_button.set_visible(row == selected_row)

        label_box = selected_row.get_children()[0]
        check_button = label_box.get_children()[0]
        if check_button.get_active():
            check_button.set_active(False)
        else:
            check_button.set_active(True)

    def refresh_label_list(self):
        all_labels = sorted(self.__main_win.docsearch.label_list)
        self._clear_label_list()
        self._readd_label_widgets(all_labels)
        for label in self.labels:
            if self.doc:
                active = label in self.doc.labels
            else:
                active = False
            self.labels[label][1].set_active(active)

    def on_keywords_focus_in(self, textarea, event):
        extra_style = self.widgets['extra_keywords'].get_style_context()
        extra_style.remove_class("extra-hint")
        text_buffer = self.widgets['extra_keywords'].get_buffer()
        text = self.get_text_from_buffer(text_buffer)
        if (text == self.default_extra_text):
            # Clear the hint
            text_buffer.set_text('')

    def on_keywords_focus_out(self, textarea, event):
        text_buffer = self.widgets['extra_keywords'].get_buffer()
        text = self.get_text_from_buffer(text_buffer)
        if (len(text) == 0) or (text == ''):
            # Add the hint back
            text_buffer.set_text(self.default_extra_text)
            extra_style = self.widgets['extra_keywords'].get_style_context()
            extra_style.add_class("extra-hint")

    def refresh_keywords_textview(self):
        """
        Display paper keywords or a hint.
        """
        extra_style = self.widgets['extra_keywords'].get_style_context()
        extra_style.remove_class("extra-hint")
        text_buffer = self.widgets['extra_keywords'].get_buffer()
        if len(self.doc.extra_text) > 0:
            text_buffer.set_text(self.doc.extra_text)
        else:
            text_buffer.set_text(self.default_extra_text)
            extra_style.add_class("extra-hint")

        self.widgets['extra_keywords'].set_buffer(text_buffer)

    def on_label_updating_start_cb(self, src):
        self.__main_win.set_search_availability(False)
        self.__main_win.set_mouse_cursor("Busy")

    def on_label_updating_doc_updated_cb(self, src, progression, doc_name):
        self.__main_win.set_progression(
            src, progression,
            _("Updating label (%s) ...") % (doc_name)
        )

    def on_label_deletion_doc_updated_cb(self, src, progression, doc_name):
        self.__main_win.set_progression(
            src, progression,
            _("Deleting label (%s) ...") % (doc_name)
        )

    def on_label_updating_end_cb(self, src):
        self.__main_win.set_progression(src, 0.0, None)
        self.__main_win.set_search_availability(True)
        self.__main_win.set_mouse_cursor("Normal")
        self.__main_win.refresh_label_list()
        self.__main_win.refresh_doc_list()
