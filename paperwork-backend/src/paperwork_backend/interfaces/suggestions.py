import abc


class SuggestionProvider(abc.ABC):
    @abc.abstractmethod
    def suggestion_get(self, out: set, sentence):
        ...
