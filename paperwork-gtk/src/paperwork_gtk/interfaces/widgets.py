import abc


class FlowLayoutFactory(abc.ABC):
    @abc.abstractmethod
    def gtk_widget_flowlayout_new(self, spacing=(0, 0)):
        ...


class LabelFactory(abc.ABC):
    @abc.abstractmethod
    def gtk_widget_label_new(self, label_txt, label_color, highlight=False):
        ...
