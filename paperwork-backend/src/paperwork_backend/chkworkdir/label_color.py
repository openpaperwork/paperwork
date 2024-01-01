import logging

import openpaperwork_core

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    """
    Label files in each document contains both the label names and their color.
    If the user changes a label color, label files are updated one-by-one.
    If this process is interrupted, we end up with 2 colors for the same
    label.
    """
    def get_interfaces(self):
        return ['chkworkdir']

    def get_deps(self):
        return [
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
        ]

    @staticmethod
    def _is_same_color(a, b):
        a = (int(a[0] * 0xFF), int(a[1] * 0xFF), int(a[2] * 0xFF))
        b = (int(b[0] * 0xFF), int(b[1] * 0xFF), int(b[2] * 0xFF))
        return a == b

    def check_work_dir(self, out_problems: list):
        all_docs = []
        self.core.call_all("storage_get_all_docs", all_docs, only_valid=False)
        all_docs.sort()

        total = len(all_docs)
        LOGGER.info("Checking work directory (%d documents)", total)

        # label text --> (
        #     label color, first_seen_doc_id, first_seen_exact_color
        # )
        first_seen_labels = {}

        for (idx, (doc_id, doc_url)) in enumerate(all_docs):
            self.core.call_all(
                "on_progress", "chkworkdir_label_color",
                idx / total, _("Checking doc %s") % (doc_id,)
            )

            doc_labels = set()
            self.core.call_all("doc_get_labels_by_url", doc_labels, doc_url)
            for (doc_label_txt, doc_label_color_orig) in doc_labels:
                doc_label_color = self.core.call_success(
                    "label_color_to_rgb", doc_label_color_orig
                )

                first_color = first_seen_labels.get(doc_label_txt, None)
                if first_color is None:
                    first_seen_labels[doc_label_txt] = (
                        doc_label_color, doc_id, doc_label_color_orig
                    )
                    continue

                (first_color, first_docid, first_exact_color) = first_color
                if self._is_same_color(first_color, doc_label_color):
                    continue

                out_problems.append({
                    "problem": "label_color",
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "problem_color": doc_label_color,
                    "solution_color": first_color,
                    "current_label": (doc_label_txt, doc_label_color),
                    "fixed_label": (doc_label_txt, first_exact_color),
                    "human_description": {
                        "problem": (
                            _(
                                "Document %s has label \"%s\" with color=%s"
                                " while document %s has label"
                                " \"%s\" with color=%s"
                            ) % (
                                doc_id, doc_label_txt,
                                self.core.call_success(
                                    "label_color_rgb_to_text",
                                    doc_label_color
                                ),
                                first_docid,
                                doc_label_txt,
                                self.core.call_success(
                                    "label_color_rgb_to_text",
                                    first_color
                                )
                            )
                        ),
                        "solution": (
                            _(
                                "Set label color %s on label \"%s\""
                                " of document %s"
                            )
                            % (
                                self.core.call_success(
                                    "label_color_rgb_to_text",
                                    first_color
                                ),
                                doc_label_txt, doc_id
                            )
                        )
                    }
                })

        self.core.call_all("on_progress", "chkworkdir_label_color", 1.0)

    def fix_work_dir(self, problems):
        total = len(problems)
        for (idx, problem) in enumerate(problems):
            if problem['problem'] != 'label_color':
                continue
            LOGGER.info("Fixing document %s", problem['doc_url'])
            self.core.call_all(
                "on_progress", "fixworkdir_label_color",
                idx / total, _("Fixing label on doc %s") % (problem['doc_id'],)
            )
            self.core.call_success(
                "doc_remove_label_by_url", problem['doc_url'],
                problem['current_label'][0]
            )
            self.core.call_success(
                "doc_add_label_by_url", problem['doc_url'],
                problem['fixed_label'][0], problem['fixed_label'][1]
            )
        self.core.call_all("on_progress", "fixworkdir_label_color", 1.0)
