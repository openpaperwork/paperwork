import abc


class Chkworkdir(abc.ABC):
    @abc.abstractmethod
    def check_work_dir(self, out_problems: list):
        ...

    @abc.abstractmethod
    def fix_work_dir(self, problems):
        ...
