import abc


class DocLabelListener(abc.ABC):
    @abc.abstractmethod
    def on_label_loading_start(self):
        ...

    @abc.abstractmethod
    def on_label_loading_end(self):
        ...


class DocLabels(abc.ABC):
    @abc.abstractmethod
    def doc_has_labels_by_url(self, doc_url):
        ...

    @abc.abstractmethod
    def doc_get_labels_by_url(self, out: set, doc_url):
        ...

    @abc.abstractmethod
    def doc_get_labels_by_url_promise(self, out: list, doc_url):
        ...

    @abc.abstractmethod
    def doc_add_label_by_url(self, doc_url, label, color=None):
        ...

    @abc.abstractmethod
    def doc_remove_label_by_url(self, doc_url, label):
        ...

    @abc.abstractmethod
    def labels_get_all(self, out: set):
        ...

    @abc.abstractmethod
    def label_load_all(self, promises: list):
        ...


class DocLabelColors(abc.ABC):
    @abc.abstractmethod
    def label_generate_color(self):
        ...

    @abc.abstractmethod
    def label_get_foreground_color(self, bg_color):
        ...

    @abc.abstractmethod
    def label_color_to_rgb(self, color):
        ...

    @abc.abstractmethod
    def label_color_from_rgb(self, color):
        ...

    @abc.abstractmethod
    def label_color_rgb_to_text(self, color):
        ...
