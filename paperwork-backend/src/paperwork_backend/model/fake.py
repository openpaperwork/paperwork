import datetime
import time

import openpaperwork_core

from . import workdir


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def __init__(self):
        super().__init__()
        # expected in self.docs:
        # [
        #   {
        #     'id': 'some_id',
        #     'url': 'file:///some_work_dir/some_id',
        #     'mtime': 12345,  # unix timestamp
        #     'labels': [(label_name, label_color), ...]
        #     'hash': 12345,  # optional
        #     'text': "pouet",  # optional
        #     'page_boxes: [  # optional
        #       [LineBox, LineBox, ...],  # page 0
        #       [LineBox, LineBox, ...],  # page 1
        #       (...)
        #     ],
        #     'page_imgs': [  # optional
        #       (img_url, PIL.Image),  # page 0
        #       (img_url, PIL.Image),  # page 1
        #     ],
        #     'page_mtimes': [  # optional
        #       (img_url, mtime),  # page 0
        #       (img_url, mtime),  # page 1
        #     ],
        #     'page_hashes': [  # optional
        #       (img_url, hash),  # page 0
        #       (img_url, hash),  # page 1
        #     ],
        #     'page_paper_sizes': [  # optional
        #       (img_url, hash),  # page 0
        #       (img_url, hash),  # page 1
        #     ],
        #   },
        #   (...)
        # ]
        self.docs = []
        self.new_doc_idx = 0

    def get_interfaces(self):
        return [
            "doc_hash",
            "doc_labels",
            "doc_text",
            "doc_type",
            "document_storage",
            "page_boxes",
            "page_paper",
            "pillow",
        ]

    def get_deps(self):
        return []

    def storage_get_id(self):
        return "file:///home/jflesch/papers"

    def storage_get_all_docs(self, out: list, only_valid=True):
        out += [
            (doc['id'], doc['url'])
            for doc in self.docs
        ]

    def doc_id_to_url(self, doc_id, existing=True):
        for doc in self.docs:
            if doc['id'] == doc_id:
                return doc['url']
        return None

    def doc_url_to_id(self, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                return doc['id']
        return None

    def is_doc(self, doc_url):
        return True

    def doc_get_hash_by_url(self, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if 'hash' in doc:
                    return doc['hash']

    def doc_get_mtime_by_url(self, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                return doc['mtime']

    def doc_get_nb_pages_by_url(self, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                l_boxes = len(doc['page_boxes']) if 'page_boxes' in doc else 0
                l_imgs = len(doc['page_imgs']) if 'page_imgs' in doc else 0
                l_mtimes = (
                    len(doc['page_mtimes']) if 'page_mtimes' in doc else 0
                )
                l_hashes = (
                    len(doc['page_hashes']) if 'page_hashes' in doc else 0
                )
                l_paper_sizes = (
                    len(doc['page_paper_sizes'])
                    if 'page_paper_sizes' in doc else 0
                )
                return max(l_boxes, l_imgs, l_mtimes, l_hashes, l_paper_sizes)
        return None

    def doc_get_text_by_url(self, out: list, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                out.append(doc['text'])

    def doc_get_labels_by_url(self, out: set, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                out.update(doc['labels'])

    def doc_has_labels_by_url(self, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                return True if len(doc["labels"]) > 0 else None
        return None

    def doc_add_label_by_url(self, doc_url, label, color=None):
        if color is None:
            all_labels = set()
            self.labels_get_all(all_labels)

            for (label_name, c) in all_labels:
                if label_name == label:
                    color = c
                    break
            else:
                raise Exception(
                    "label {} provided without color,"
                    " but label is unknown".format(label)
                )

        for doc in self.docs:
            if doc['url'] == doc_url:
                doc['labels'].add((label, color))

        return True

    def page_has_text_by_url(self, doc_url, page_idx):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if page_idx >= len(doc['page_boxes']):
                    return None
                return True
        return None

    def page_get_boxes_by_url(self, doc_url, page_idx):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if page_idx >= len(doc['page_boxes']):
                    return None
                return doc['page_boxes'][page_idx]
        return None

    def page_set_boxes_by_url(self, doc_url, page_idx, boxes):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if page_idx >= len(doc['page_boxes']):
                    missing = page_idx + 1 - len(doc['page_boxes'])
                    assert missing >= 1
                    doc['page_boxes'] += ([None] * missing)
                doc['page_boxes'][page_idx] = boxes

                text = ""
                for page_boxes in doc['page_boxes']:
                    if text != "":
                        text += "\n\n"
                    if page_boxes is None:
                        continue
                    for line_boxes in page_boxes:
                        text += line_boxes.content + "\n"
                doc['text'] = text
        return True

    def page_get_img_url(self, doc_url, page_idx, write=False, **kwargs):
        for doc in self.docs:
            if doc['url'] == doc_url:
                for k in [
                            'page_imgs', 'page_mtimes', 'page_hashes',
                            'page_sizes'
                        ]:
                    if k in doc:
                        if page_idx >= len(doc[k]):
                            return None
                        return doc[k][page_idx][0]

                if write:
                    return "file:///some_doc/new_page.jpeg"
                else:
                    return None
        return None

    def url_to_pillow(self, img_url):
        for doc in self.docs:
            if 'page_imgs' not in doc:
                continue
            for (page_img_url, img) in doc['page_imgs']:
                if page_img_url == img_url:
                    return img
        return None

    def labels_get_all(self, out: set):
        for doc in self.docs:
            out.update(doc['labels'])

    def storage_get_new_doc(self):
        self.new_doc_idx += 1
        doc = {
            'url': 'file:///some_work_dir/{}'.format(self.new_doc_idx),
            'id': str(self.new_doc_idx),
            'mtime': time.time(),
            'labels': [],
        }
        self.docs.append(doc)
        return (doc['id'], doc['url'])

    def doc_get_date_by_id(self, doc_id):
        # Doc id is expected to have this format:
        # YYYYMMDD_hhmm_ss_NN_something_else
        doc_id = doc_id.split("_", 3)
        doc_id = "_".join(doc_id[:3])
        try:
            return datetime.datetime.strptime(doc_id, workdir.DOCNAME_FORMAT)
        except ValueError:
            return None

    def storage_delete_doc_id(self, doc_id):
        for (idx, doc) in enumerate(self.docs[:]):
            if doc['id'] == doc_id:
                self.docs.pop(idx)
                return True

    def page_delete(self, doc_url, page_idx):
        raise NotImplementedError()

    def page_get_mtime_by_url(self, doc_url, page_idx):
        for doc in self.docs:
            if doc['url'] != doc_url:
                continue
            if 'page_mtimes' not in doc:
                continue
            return doc['page_mtimes'][page_idx][1]

    def page_get_hash_by_url(self, doc_url, page_idx):
        for doc in self.docs:
            if doc['url'] != doc_url:
                continue
            if 'page_hashes' not in doc:
                continue
            return doc['page_hashes'][page_idx][1]

    def page_get_paper_size_by_url(self, doc_url, page_idx):
        for doc in self.docs:
            if doc['url'] != doc_url:
                continue
            if 'page_paper_sizes' not in doc:
                continue
            return doc['page_paper_sizes'][page_idx][1]
