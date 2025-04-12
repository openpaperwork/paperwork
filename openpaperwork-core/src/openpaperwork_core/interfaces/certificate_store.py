import abc


class CertificateStore(abc.ABC):
    @abc.abstractmethod
    def store_certificate_get(self, name):
        ...

    @abc.abstractmethod
    def store_certificate_get_fingerprint(self, name):
        ...

    @abc.abstractmethod
    def store_certificate_get_promise(self, name):
        ...

    @abc.abstractmethod
    def store_certificate_generate(self, name, parent=None, embed_key=False):
        ...

    @abc.abstractmethod
    def store_certificate_generate_promise(self, name, parent=None):
        ...
