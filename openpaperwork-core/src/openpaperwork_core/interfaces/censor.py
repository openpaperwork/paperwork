import abc


class Censor(abc.ABC):
    @abc.abstractmethod
    def censor_string(self, string):
        ...

    @abc.abstractmethod
    def censor_txt_file(self, input_url, output_url=None, tmp_on_disk=False) -> str:
        ...
