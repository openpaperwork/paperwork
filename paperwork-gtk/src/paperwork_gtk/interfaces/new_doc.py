import abc


class NewDoc(abc.ABC):
    @abc.abstractmethod
    def get_new_doc(self):
        ...
