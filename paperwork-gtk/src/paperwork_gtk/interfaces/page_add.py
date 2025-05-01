import abc


class PageAddButtons(abc.ABC):
    @abc.abstractmethod
    def pageadd_buttons_set_source_popover(self, selector):
        ...

    @abc.abstractmethod
    def pageadd_set_default_action(self, txt, callback, *args):
        ...

    @abc.abstractmethod
    def pageadd_busy_add(self):
        ...

    @abc.abstractmethod
    def pageadd_busy_remove(self):
        ...


class PageAddButtonsSources(abc.ABC):
    @abc.abstractmethod
    def pageadd_get_sources(self, out: list):
        ...


class PageAddButtonsSourcesPopover(abc.ABC):
    @abc.abstractmethod
    def pageadd_sources_refresh(self):
        ...
