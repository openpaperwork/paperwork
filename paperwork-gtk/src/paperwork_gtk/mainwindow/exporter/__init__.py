import logging
import random

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps

import paperwork_backend.docexport

from ... import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.ui = None
        self.active_doc = None
        self.active_page_idx = None
        self.windows = []

        self.button_validate = None
        self.button_send_email = None
        self.preciew = None
        self.zoom = None
        self.quality = None
        self.combobox_page_format = None
        self.model_page_format = None

        # The reference ('ref_*') is what is displayed as example to the user.
        # It's always only one page. The exported document size is estimated
        # by multiplying this reference page after post-processing by the
        # number of pages in the document.

        # Inputs (export_input_*) refer to export pipe inputs
        # (see paperwork_backend.docexport)

        self.ref_input_page = None
        self.ref_input_doc = None
        self.export_input_type = None
        self.export_input = None
        self.export_input_doc_urls = None
        self.need_zoom_auto = True

        self.pipeline = []
        self.renderer = None
        self.tmp_file_url = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_open',
            'gtk_exporter',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'cairo_url',
                'defaults': [
                    'paperwork_backend.cairo.pillow',
                    'paperwork_backend.cairo.poppler',
                ],
            },
            {
                'interface': 'export_pipes',
                'defaults': [
                    'paperwork_backend.docexport.img',
                    'paperwork_backend.docexport.pdf',
                    'paperwork_backend.docexport.pillowfight',
                ],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
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
                'interface': 'gtk_zoomable',
                'defaults': ['paperwork_gtk.gesture.zoom'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                'interface': 'notifications',
                'defaults': [
                    'paperwork_gtk.notifications.dialog',
                    'paperwork_gtk.notifications.notify',
                ],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
            {
                'interface': 'external_apps',
                'defaults': [
                    'openpaperwork_core.external_apps.dbus',
                    'openpaperwork_core.external_apps.windows',
                    'openpaperwork_core.external_apps.xdg',
                ],
            },
        ]

    def init(self, core):
        super().init(core)

        opt = self.core.call_success(
            "config_build_simple", "GUI", "last_export_uri",
            lambda: None
        )
        self.core.call_all("config_register", "last_export_uri", opt)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.exporter", "exporter.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.widget_tree.get_object("exporter_cancel").connect(
            "clicked", self._on_cancel
        )
        self.button_validate = self.widget_tree.get_object("exporter_validate")
        self.button_validate.connect(
            "clicked", self._on_apply
        )
        self.button_send_email = self.widget_tree.get_object(
            "exporter_send_email"
        )
        self.button_send_email.connect(
            "clicked", self._on_send_email
        )
        can_send_as_attachment = core.call_success(
            "external_app_can_send_as_attachment"
        )
        if not can_send_as_attachment:
            self.button_send_email.set_visible(False)

        self.zoom = self.widget_tree.get_object("exporter_zoom_adjustment")
        self.zoom.connect("value-changed", self._on_zoom_changed)

        self.quality = self.widget_tree.get_object(
            "exporter_quality_adjustment"
        )
        self.quality.connect("value-changed", self._on_quality_changed)

        self.preview = self.widget_tree.get_object("exporter_img")
        self.preview.connect("draw", self._on_draw)

        self.core.call_all(
            "on_zoomable_widget_new",
            self.widget_tree.get_object("exporter_scroll"),
            self.zoom
        )

        self.core.call_all(
            "mainwindow_add", "right", "exporter", prio=0,
            header=self.widget_tree.get_object("exporter_header"),
            body=self.widget_tree.get_object("exporter_body")
        )

        self.core.call_success("work_queue_create", "exporter")

        self.combobox_page_format = self.widget_tree.get_object(
            "exporter_page_format"
        )
        self.model_page_format = self.widget_tree.get_object(
            "exporter_page_format_model"
        )

        self._add_page_formats()

        self.combobox_page_format.connect(
            "changed", self._on_page_format_changed
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _add_page_formats(self):
        default_idx = -1
        for (idx, paper_size) in enumerate(
                Gtk.PaperSize.get_paper_sizes(True)):
            store_data = (
                paper_size.get_display_name(),
                paper_size.get_width(Gtk.Unit.POINTS),
                paper_size.get_height(Gtk.Unit.POINTS)
            )
            self.model_page_format.append(store_data)
            if paper_size.get_name() == paper_size.get_default():
                default_idx = idx
        if default_idx >= 0:
            self.combobox_page_format.set_active(default_idx)

    def _get_possible_pipes(self, input_type, active_pipe=""):
        pipes = []
        if input_type == paperwork_backend.docexport.ExportDataType.DOCUMENT:
            self.core.call_all(
                "export_get_pipes_by_doc_urls",
                pipes, self.export_input_doc_urls
            )
        else:
            self.core.call_all("export_get_pipes_by_input", pipes, input_type)
        pipeline = {p.name for p in self.pipeline}
        if active_pipe in pipeline:
            pipeline.remove(active_pipe)
        pipes = [p for p in pipes if p.name not in pipeline]
        return pipes

    def _expand_pipeline(self):
        """
        When there is only once choice possible, this isn't really a choice.
        --> we expand automatically the pipeline to include the only choice
        possible.
        """
        while True:
            if len(self.pipeline) > 0:
                last_output_type = self.pipeline[-1].output_type
            else:
                last_output_type = self.export_input_type

            if last_output_type == 'file_url':
                # pipeline is complete
                return

            pipes = self._get_possible_pipes(last_output_type)
            if len(pipes) != 1:
                # there is a choice (or none at all), nothing to do
                return
            pipe = pipes[0]
            assert pipe.name not in (p.name for p in self.pipeline)
            self.pipeline.append(pipe)
            LOGGER.info("Pipeline expanded: %s", [
                p.name for p in self.pipeline
            ])

    def _add_combobox(self, steps, previous_input_type, active_pipe):
        possible_alternative_pipes = self._get_possible_pipes(
            previous_input_type, active_pipe
        )
        if len(possible_alternative_pipes) <= 1:
            # not really a choice
            return

        possible_alternative_pipes.sort(key=lambda p: str(p))

        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.exporter", "pipe.glade"
        )
        combobox = widget_tree.get_object("exporter_pipe")
        choices = widget_tree.get_object("exporter_pipe_model")
        choices.clear()
        choices.append((_("Please select the next export step"), ""))
        active_idx = 0
        for (alternative_idx, alternative_pipe) in enumerate(
                possible_alternative_pipes):
            choices.append(
                (str(alternative_pipe), alternative_pipe.name)
            )
            if alternative_pipe.name == active_pipe:
                active_idx = alternative_idx + 1
        combobox.set_active(active_idx)
        combobox.connect('changed', self._on_pipeline_changed)
        steps.add(combobox)

    def _refresh_pipeline_ui(self):
        LOGGER.info("Displaying pipeline: %s", [p.name for p in self.pipeline])
        steps = self.widget_tree.get_object("exporter_steps")
        for widget in steps:
            steps.remove(widget)

        for (pipe_idx, pipe) in enumerate(self.pipeline):
            if pipe_idx <= 0:
                previous_input_type = self.export_input_type
            else:
                previous_input_type = self.pipeline[pipe_idx - 1].output_type
            self._add_combobox(steps, previous_input_type, pipe.name)

        if len(self.pipeline) > 0:
            last_output_type = self.pipeline[-1].output_type
            LOGGER.info(
                "Last pipe: %s ; Last output type: %s",
                self.pipeline[-1], last_output_type
            )
        else:
            last_output_type = self.export_input_type
            LOGGER.info("Input type: %s", last_output_type)

        t = paperwork_backend.docexport.ExportDataType.OUTPUT_URL_FILE
        if last_output_type == t:
            self.button_validate.set_sensitive(True)
            self.button_send_email.set_sensitive(True)
        else:
            self._add_combobox(steps, last_output_type, "")
            self.button_validate.set_sensitive(False)
            self.button_send_email.set_sensitive(False)

    def _rebuild_pipeline_from_ui(self):
        LOGGER.info("Rebuilding pipeline from UI")
        self.pipeline = []
        steps = self.widget_tree.get_object("exporter_steps")
        for combobox in steps:
            self._expand_pipeline()
            pipe = combobox.get_active()
            pipe = combobox.get_model()[pipe][1]
            if pipe == "":
                return
            pipe = self.core.call_success("export_get_pipe_by_name", pipe)
            if len(self.pipeline) > 0:
                if self.pipeline[-1].output_type != pipe.input_type:
                    LOGGER.warning(
                        "Pipe [%s] cannot be followed [%s]. Ignoring"
                        " remainder of the pipeline",
                        self.pipeline[-1], pipe
                    )
                    break
            self.pipeline.append(pipe)
        LOGGER.info("Pipeline from UI: %s", [p.name for p in self.pipeline])

    def _hide_preview(self):
        if self.tmp_file_url is not None:
            self.core.call_success("fs_unlink", self.tmp_file_url, trash=False)
            self.tmp_file_url = None
        if self.renderer is not None:
            self.renderer.close()
            self.renderer = None
        label = self.widget_tree.get_object("exporter_estimated_size")
        label.set_text("")
        label.set_visible(False)

    def _resize_preview(self):
        self.preview.set_size_request(
            int(self.renderer.size[0] * self.renderer.zoom),
            int(self.renderer.size[1] * self.renderer.zoom)
        )

    def _on_size_obtained(self, *args, **kwargs):
        if self.need_zoom_auto:
            allocation = self.widget_tree.get_object(
                "exporter_scroll"
            ).get_allocation()
            allocation = (allocation.width - 20, allocation.height - 20)
            zoom = min(
                allocation[0] / self.renderer.size[0],
                allocation[1] / self.renderer.size[1],
            )
            self.zoom.set_value(zoom)
            self.renderer.zoom = zoom
            self.need_zoom_auto = False
        self._resize_preview()

    def _redraw_preview(self, renderer):
        self.preview.queue_draw()

    def _show_preview(self, tmp_file_urls):
        tmp_file_url = list(tmp_file_urls)[0]
        LOGGER.info("Preview: %s", tmp_file_url)
        self.tmp_file_url = tmp_file_url
        self.renderer = self.core.call_success(
            "cairo_renderer_by_url", "exporter", tmp_file_url
        )
        self.renderer.zoom = self.zoom.get_value()
        self.renderer.connect("size_obtained", self._on_size_obtained)
        self.renderer.connect("img_obtained", self._redraw_preview)
        self.renderer.start()
        self.renderer.render()
        return tmp_file_url

    def _show_estimated_size(self, tmp_file_url):
        preview_size = self.core.call_success("fs_getsize", tmp_file_url)
        factors = (
            p.get_estimated_size_factor(self.export_input)
            for p in self.pipeline
        )
        final_size = preview_size
        for f in factors:
            final_size *= f
        LOGGER.info(
            "Preview size: %d ; Estimated final size: %d",
            preview_size, final_size
        )
        final_size = self.core.call_success("i18n_file_size", final_size)
        label_txt = _("Estimated file size: %s") % (final_size)
        label = self.widget_tree.get_object("exporter_estimated_size")
        label.set_text(label_txt)
        label.set_visible(True)
        return tmp_file_url

    def _get_pipe_plug(self):
        if self.pipeline[-1].output_type == 'pages':
            return self.core.call_success(
                "export_get_pipe_by_name", "png"
            )
        return None

    def _set_quality(self):
        can_change_quality = False
        for pipe in self.pipeline:
            if not pipe.can_change_quality:
                continue
            can_change_quality = True
            pipe.set_quality(self.quality.get_value() / 100)

        self.widget_tree.get_object("exporter_quality").set_sensitive(
            can_change_quality
        )
        self.widget_tree.get_object("exporter_quality_label").set_sensitive(
            can_change_quality
        )

    def _set_page_format(self):
        page_format = self.combobox_page_format.get_active()
        page_format = self.model_page_format[page_format]

        can_change_page_format = False
        for pipe in self.pipeline:
            if not pipe.can_change_page_format:
                continue
            can_change_page_format = True
            pipe.set_page_format((page_format[1], page_format[2]))

        self.widget_tree.get_object("exporter_page_format").set_sensitive(
            can_change_page_format
        )
        self.widget_tree.get_object(
            "exporter_page_format_label"
        ).set_sensitive(
            can_change_page_format
        )

    def _reload_preview(self):
        self.core.call_all("work_queue_cancel_all", "exporter")

        promise = openpaperwork_core.promise.Promise(
            self.core, self._hide_preview
        )

        if len(self.pipeline) <= 0:
            self.core.call_success(
                "work_queue_add_promise", "exporter", promise
            )
            return

        # some pipeline only accepts ExportDataType.DOCUMENT as input,
        # other accept ExportDataType.PAGE, but not immediately.
        # For the preview, we prefer ExportDataType.PAGE,
        # if not available we fall back to ExportDataType.DOCUMENT
        for (idx, pipe) in enumerate(self.pipeline):
            if (pipe.input_type ==
                    paperwork_backend.docexport.ExportDataType.PAGE):
                pipeline = self.pipeline[idx:]
                ref_input = self.ref_input_page
                break
        else:
            for (idx, pipe) in enumerate(self.pipeline):
                if (pipe.input_type ==
                        paperwork_backend.docexport.ExportDataType.DOCUMENT):
                    pipeline = self.pipeline[idx:]
                    ref_input = self.ref_input_doc
                    break
            else:
                LOGGER.warning(
                    "Can't display export preview:"
                    " No matching input pipe found in %s",
                    [str(p) for p in self.pipeline]
                )
                return

        ref_input = ref_input.clone()

        pipe_plug = self._get_pipe_plug()
        if pipe_plug is not None:
            if pipe_plug.can_change_quality:
                pipe_plug.set_quality(self.quality.get_value() / 100)
            if pipe_plug.can_change_page_format:
                page_format = self.combobox_page_format.get_active()
                page_format = self.model_page_format[page_format]
                pipe_plug.set_page_format((page_format[1], page_format[2]))

        t = paperwork_backend.docexport.ExportDataType.OUTPUT_URL_FILE
        if pipe_plug is None and pipeline[-1].output_type != t:
            LOGGER.warning(
                "Can't display export preview: unexpected pipe end: %s",
                pipeline[-1].output_type
            )
            self.core.call_success(
                "work_queue_add_promise", "exporter", promise
            )
            return

        promise = promise.then(self.core.call_all, "on_busy")
        promise = promise.then(lambda *args, **kwargs: ref_input)
        for pipe in pipeline:
            promise = promise.then(pipe.get_promise(result='preview'))
        if pipe_plug is not None:
            promise = promise.then(pipe_plug.get_promise(result='preview'))
        promise = promise.then(self._show_preview)
        if pipe_plug is None:
            promise = promise.then(self._show_estimated_size)
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_all, "on_idle")
        self.core.call_success("work_queue_add_promise", "exporter", promise)

    def _gtk_open_exporter(self):
        self.pipeline = []
        self.need_zoom_auto = True

        self._expand_pipeline()
        self._refresh_pipeline_ui()
        self._set_quality()
        self._set_page_format()
        self._reload_preview()
        self.core.call_all("mainwindow_show", "right", "exporter")

    def gtk_open_exporter(self, doc_id, doc_url, page_idx=None):
        ref_page_idx = 0
        if page_idx is not None:
            ref_page_idx = page_idx
        elif doc_url == self.active_doc[1]:
            ref_page_idx = self.active_page_idx

        self.ref_input_page = (
            paperwork_backend.docexport.ExportData.build_page(
                doc_id, doc_url, ref_page_idx
            )
        )
        self.ref_input_doc = (
            paperwork_backend.docexport.ExportData.build_doc(doc_id, doc_url)
        )

        self.export_input_type = (
            paperwork_backend.docexport.ExportDataType.DOCUMENT
            if page_idx is None else
            paperwork_backend.docexport.ExportDataType.PAGE
        )
        self.export_input = (
            paperwork_backend.docexport.ExportData.build_doc(doc_id, doc_url)
            if page_idx is None else
            paperwork_backend.docexport.ExportData.build_page(
                doc_id, doc_url, page_idx
            )
        )
        self.export_input_doc_urls = [doc_url]
        self._gtk_open_exporter()

    def gtk_open_exporter_multiple_docs(
            self, docs, ref_doc_id, ref_doc_url, ref_page_idx):
        self.ref_input_page = (
            paperwork_backend.docexport.ExportData.build_page(
                ref_doc_id, ref_doc_url, ref_page_idx
            )
        )
        self.ref_input_doc = (
            paperwork_backend.docexport.ExportData.build_doc(
                ref_doc_id, ref_doc_url
            )
        )

        self.export_input_type = (
            paperwork_backend.docexport.ExportDataType.DOCUMENT_SET
        )
        self.export_input = (
            paperwork_backend.docexport.ExportData.build_doc_set(docs)
        )
        self.export_input_doc_urls = [doc[1] for doc in docs]
        self._gtk_open_exporter()

    def _on_draw(self, drawing_area, cairo_context):
        if self.renderer is None:
            return
        self.renderer.draw(cairo_context)

    def _on_zoom_changed(self, adj):
        if self.renderer is None:
            return
        self.renderer.zoom = adj.get_value()
        self._resize_preview()
        self.preview.queue_draw()

    def _on_quality_changed(self, adj):
        self._set_quality()
        self._reload_preview()

    def _on_page_format_changed(self, combobox):
        self._set_page_format()
        self._reload_preview()

    def _on_pipeline_changed(self, *args, **kwargs):
        self._rebuild_pipeline_from_ui()
        self._expand_pipeline()
        # WORKAROUND(JFlesch): call this method using mainloop_schedule.
        # Otherwise, in Flatpak, with Gnome 40, it crashes.
        self.core.call_one("mainloop_schedule", self._refresh_pipeline_ui)
        self._set_quality()
        self._set_page_format()
        self._reload_preview()

    def _on_cancel(self, button):
        LOGGER.info("Export canceled")
        self.core.call_all("mainwindow_back", side="right")

    def _on_apply(self, button):
        LOGGER.info("Export settings defined. Opening file chooser dialog")

        dialog = Gtk.FileChooserNative.new(
            _("Select a file to which export the document"),
            self.windows[-1],
            Gtk.FileChooserAction.SAVE,
            None, None
        )
        dialog.set_modal(True)
        dialog.set_local_only(False)

        file_filter = Gtk.FileFilter()
        file_filter.set_name(_("Any files"))
        file_filter.add_pattern("*.*")
        dialog.add_filter(file_filter)

        (mime, file_extensions) = self.pipeline[-1].get_output_mime()
        file_filter = Gtk.FileFilter()
        file_filter.add_mime_type(mime)
        file_filter.set_name(file_extensions[0])  # TODO(Jflesch): better name
        dialog.add_filter(file_filter)
        dialog.set_filter(file_filter)

        last_export_uri = self.core.call_success(
            "config_get", "last_export_uri"
        )
        if last_export_uri is not None:
            # this filename does not exist, but the parent directory
            # will be selected. A hack inspired by what firefox does.
            dialog.set_uri(last_export_uri + str(random.randint(0, 10000)))

        dialog.connect("response", self._on_dialog_response)
        dialog.run()
        dialog.hide()
        dialog.destroy()

    def _on_dialog_response(self, dialog, response_id):
        if (response_id != Gtk.ResponseType.ACCEPT and
                response_id != Gtk.ResponseType.OK and
                response_id != Gtk.ResponseType.YES and
                response_id != Gtk.ResponseType.APPLY):
            LOGGER.info("User canceled (response_id=%d)", response_id)
            return

        selected = dialog.get_uris()[0]
        self.core.call_all("mainwindow_back", side="right")

        # make sure the file extension is set
        (mime, file_extensions) = self.pipeline[-1].get_output_mime()
        for file_extension in file_extensions:
            if selected.lower().endswith(file_extension):
                break
        else:
            selected += "." + file_extensions[0]

        self.core.call_all("config_put", "last_export_uri", selected)

        promise = openpaperwork_core.promise.Promise(
            self.core, lambda: self.export_input
        )
        for pipe in self.pipeline:
            promise = promise.then(pipe.get_promise(
                result='final', target_file_url=selected
            ))
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(Gtk.RecentManager().add_item, selected)
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.catch(self._on_error)

        # do not use the work queue ; must never be canceled
        promise.schedule()

    def _on_send_email(self, button):
        (_, file_extensions) = self.pipeline[-1].get_output_mime()
        (target_file_url, fd) = self.core.call_success(
            "fs_mktemp", suffix="." + file_extensions[0], on_disk=True
        )
        fd.close()  # we only need the name
        self.core.call_all("mainwindow_back", side="right")

        promise = openpaperwork_core.promise.Promise(
            self.core, lambda: self.export_input
        )
        for pipe in self.pipeline:
            promise = promise.then(pipe.get_promise(
                result='final', target_file_url=target_file_url
            ))
        promise = promise.then(lambda *args, **kwargs: self.core.call_success(
            "external_app_send_as_attachment", target_file_url
        ))
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.catch(self._on_error)

        # do not use the work queue ; must never be canceled
        promise.schedule()

    def _on_error(self, exc):
        LOGGER.error("Export failed", exc_info=exc)
        notif = self.core.call_success(
            "get_notification_builder",
            _("Export has failed"),
        )
        notif.set_message(f"Export has failed: {type(exc)} {exc}")
        notif.set_icon("dialog-error")
        notif.show()
