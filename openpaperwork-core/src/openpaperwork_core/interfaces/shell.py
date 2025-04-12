import abc


class Shell(abc.ABC):
    def cmd_set_console(self, console):
        ...

    @abc.abstractmethod
    def cmd_complete_argparse(self, parser):
        ...

    @abc.abstractmethod
    def cmd_run(self, console, args):
        ...
