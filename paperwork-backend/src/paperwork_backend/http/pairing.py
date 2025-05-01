from collections.abc import Iterable
from typing import List
from typing import Optional
from typing import Tuple
import base64
import io
import json
import logging
import math
import secrets
import struct
import time

import PIL
import qrcode
import qrcode.image.pil

from openpaperwork_core.interfaces.certificate_store import CertificateStore
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.networking import Networking
import openpaperwork_core

from paperwork_backend.interfaces.http import HttpBackendExtension
from paperwork_backend.interfaces.http import HttpsBackend
from paperwork_backend.interfaces.http import HttpsBackendSsl
from paperwork_backend.interfaces.http import Pairing
from paperwork_backend.interfaces.http import PairingQrCode
import paperwork_backend.http


PATH = "/pair"
PROTOCOL_VERSION = 0
PNG_SUBPAYLOAD_SIZES = 256


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    HttpBackendExtension,
    HttpsBackendSsl,
    Pairing,
    PairingQrCode,
):
    PRIORITY = -100

    QRCODE_VERSIONS = [
        (21, 21),
        (25, 25),
        (29, 29),
        (33, 33),
        (37, 37),
        (41, 41),
    ]

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": Config,
                "defaults": ["openpaperwork_core.config"],
            },
            {
                "interface": CertificateStore,
                "defaults": ["openpaperwork_core.crypto.certificates.store"],
            },
            {
                "interface": Fs,
                "defaults": ["openpaperwork_gtk.fs.gio"],
            },
            {
                "interface": HttpsBackend,
                "defaults": ["paperwork_backend.http"],
            },
            {
                "interface": Networking,
                "defaults": ["openpaperwork_core.networking"],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.secret = None
        self.pairing_done = False

    def _get_qrcodes_payload(self) -> bytes:
        cert_fingerprint = self.core.call_success(
            HttpsBackend.https_backend_get_server_certificate_fingerprint
        )
        if self.secret is None:
            self.secret = secrets.token_bytes(nbytes=16)
        port = self.core.call_success(Config.config_get, "https_port")
        addresses = self.core.call_success(Networking.networking_get_host_names)
        addresses += self.core.call_success(Networking.networking_get_local_ips)
        addresses = [str(addr).encode("utf-8") for addr in addresses]
        addresses = b"\0".join(addresses)

        payload = struct.pack("!H", len(cert_fingerprint)) + cert_fingerprint
        payload += struct.pack("!H", len(self.secret)) + self.secret
        payload += struct.pack("!H", port)
        payload += addresses
        LOGGER.info("Payload: %d bytes", len(payload))
        return payload

    def _split_payload(self, payload: bytes, max_bytes_per_subpayload: int) -> Iterable[bytes]:
        max_bytes_per_subpayload -= 3

        total = math.ceil(len(payload) / max_bytes_per_subpayload)

        subpayloads = (
            (
                struct.pack("!bbb", PROTOCOL_VERSION, idx, total)
                + payload[pos:pos + max_bytes_per_subpayload]
            )
            for (idx, pos) in enumerate(range(0, len(payload), max_bytes_per_subpayload))
        )
        return subpayloads

    def pairing_qrcode_get_images(self) -> List[PIL.Image]:
        payload = self._get_qrcodes_payload()
        subpayloads = self._split_payload(payload, PNG_SUBPAYLOAD_SIZES)
        qrcodes = []
        for subpayload in subpayloads:
            qr = qrcode.QRCode()
            qr.add_data(subpayload)
            qr = qr.make_image(qrcode.image.pil.PilImage)
            qrcodes.append(qr)
        LOGGER.info("%d image QRCodes generated", len(qrcodes))
        return qrcodes

    def _get_max_qrcode_version(self, term_size: Tuple[int, int]) -> int:
        qr = [
            (version + 1, size)
            for (version, size) in enumerate(self.QRCODE_VERSIONS)
        ]
        for (qr_version, (qr_w, qr_h)) in reversed(qr):
            if term_size[0] >= qr_w and term_size[1] >= qr_h:
                break
        else:
            qr_version = len(self.QRCODE_VERSIONS)
        LOGGER.info(
            "Terminal size %dx%d --> QRCode version: %d",
            term_size[0], term_size[1], qr_version
        )
        return qr_version

    def _try_qrcode(self, payload, max_version):
        qr = qrcode.QRCode(version=max_version)
        qr.add_data(payload)
        qr.make()
        r = (qr.version <= max_version)
        LOGGER.info(
            "Trying QRCode(version=%s) with %d bytes: %s",
            max_version, len(payload),
            "fit" if r else "doesn't fit"
        )
        return r

    def _guess_qrcode_capacity(self, payload, version):
        """
        Guess the QRCode capacity by dichotomy.

        QRCode capacity depends on the QRCode version and its error correction
        code level. We could hard-code a list of qrcode capacities by version,
        but this way seemed less annoying for me :-)
        """

        payload = b"abcd" + payload  # add 4 bytes to the payload (we have a header to add later)

        smin = 0
        smax = min(len(payload), 2048)

        while True:
            if smin + 1 >= smax:
                LOGGER.info("QRCode(version=%s): capacity found: %dB", version, smin)
                return smin
            middle = int(((smax - smin) / 2) + smin)
            if self._try_qrcode(payload[:middle], version):
                # fit -> we can go upper
                smin = middle
            else:
                # does not fit -> must go lower
                smax = middle

    def pairing_qrcode_get_ascii(self, term_size: Tuple[int, int]) -> List[str]:
        qrcode_version = self._get_max_qrcode_version(term_size)
        payload = self._get_qrcodes_payload()
        qrcode_capacity = self._guess_qrcode_capacity(payload, qrcode_version)
        subpayloads = self._split_payload(payload, qrcode_capacity)
        qrcodes = []
        for subpayload in subpayloads:
            qr = qrcode.QRCode(version=qrcode_version)
            qr.add_data(subpayload)
            out = io.StringIO()
            qr.print_ascii(out)
            qr = out.getvalue()
            qrcodes.append(qr)
        LOGGER.info("%d ASCII QRCodes generated", len(qrcodes))
        return qrcodes

    def http_backend_ignore_ssl_client_cert(self, request) -> Optional[bool]:
        return True if (request.path == PATH) else None

    def http_backend_head(self, request) -> Optional[paperwork_backend.http.BackendReply]:
        if request.path != PATH:
            return None
        return paperwork_backend.http.BackendReply(
            http_code=200,
            content_type="application/json",
        )

    def http_backend_get(self, request) -> Optional[paperwork_backend.http.BackendReply]:
        if request.path != PATH:
            return None
        # basic bruteforce protection (of course, this does assume HTTPS is not multithreaded)
        time.sleep(1)

        # We expected: `Authorization: Basic <secret in base64>`
        authorization = request.headers["Authorization"]
        if authorization is None:
            LOGGER.warning("Missing HTTP header Authorization")
            return paperwork_backend.http.BackendReply(http_code=401)
        if not authorization.startswith("Basic "):
            LOGGER.warning("Authorization header doesn't start with 'Basic'")
            return paperwork_backend.http.BackendReply(http_code=401)
        try:
            authorization = authorization.split(" ", 1)[1]
            authorization = authorization.encode("utf-8")
            authorization = base64.decodebytes(authorization)
        except Exception as exc:
            LOGGER.warning("Failed to decode Authorization header", exc_info=exc)
            return paperwork_backend.http.BackendReply(http_code=401)
        if authorization != self.secret:
            LOGGER.warning("Authorization doesn't match secret")
            return paperwork_backend.http.BackendReply(http_code=401)

        (cert, key) = self.core.call_success(HttpsBackend.https_backend_get_server_certificate)
        with self.core.call_success(Fs.fs_open, cert, "r") as fd:
            server_cert = fd.read()
        (cert, key) = self.core.call_success(HttpsBackend.https_backend_get_client_certificate)
        with self.core.call_success(Fs.fs_open, cert, "r") as fd:
            client_cert = fd.read()
        with self.core.call_success(Fs.fs_open, key, "r") as fd:
            client_key = fd.read()
        content = {
            "server": {
                "certificate": server_cert,
            },
            "client": {
                "certificate": client_cert,
                "key": client_key,
            },
        }
        content = json.dumps(content)
        self.pairing_done = True
        return paperwork_backend.http.BackendReply(
            http_code=200,
            content_type="application/json",
            content_raw=content.encode("utf-8"),
        )

    def is_pairing_done(self):
        if not self.pairing_done:
            return None
        return True
