from typing import Optional
from typing import List
from typing import Tuple
import abc


class CryptoCertificates(abc.ABC):
    @abc.abstractmethod
    def crypto_generate_certificate(
        self,
        validity_time_s: int,
        hostnames: Optional[List[str]] = None,
        ip_addresses: Optional[List[str]] = None,
        parent: Optional[Tuple[bytes, bytes]] = None,
        embed_key=False
    ):
        ...

    @abc.abstractmethod
    def crypto_fingerprint_certificate(self, cert: bytes):
        ...
