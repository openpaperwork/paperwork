from typing import BinaryIO
from typing import List
from typing import Optional
from typing import Tuple
import abc
import dataclasses

import PIL


@dataclasses.dataclass
class AbstractBackendReply(abc.ABC):
    http_code: int
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    last_modified: Optional[int] = None
    etag: Optional[str] = None

    content_fd: Optional[BinaryIO] = None
    content_raw: Optional[bytes] = None

    @abc.abstractmethod
    def send(self, core, request):
        ...


class HttpsBackend(abc.ABC):
    @abc.abstractmethod
    def https_backend_reload(self):
        ...

    @abc.abstractmethod
    def https_backend_regenerate_certificates(self):
        ...

    @abc.abstractmethod
    def https_backend_get_server_certificate(self):
        ...

    @abc.abstractmethod
    def https_backend_get_server_certificate_fingerprint(self):
        ...

    @abc.abstractmethod
    def https_backend_get_client_certificate(self):
        ...


class HttpsBackendSsl(abc.ABC):
    @abc.abstractmethod
    def http_backend_ignore_ssl_client_cert(self, request) -> Optional[bool]:
        ...


class HttpBackendExtension(abc.ABC):
    @abc.abstractmethod
    def http_backend_head(self, request) -> Optional[AbstractBackendReply]:
        ...

    @abc.abstractmethod
    def http_backend_get(self, request) -> Optional[AbstractBackendReply]:
        ...


class Pairing(abc.ABC):
    @abc.abstractmethod
    def is_pairing_done(self):
        ...


class PairingQrCode(abc.ABC):
    @abc.abstractmethod
    def pairing_qrcode_get_images(self) -> List[PIL.Image]:
        ...

    @abc.abstractmethod
    def pairing_qrcode_get_ascii(self, term_size: Tuple[int, int]) -> List[str]:
        ...
