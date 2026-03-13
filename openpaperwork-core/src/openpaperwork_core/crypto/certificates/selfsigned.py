#!/usr/bin/python3

from typing import List
from typing import Optional
from typing import Tuple
import datetime
import logging
import os

os.environ["CRYPTOGRAPHY_OPENSSL_NO_LEGACY"] = "1"

import cryptography  # noqa E402
import cryptography.hazmat.backends  # noqa E402
import cryptography.hazmat.primitives.asymmetric.rsa  # noqa E402
import cryptography.hazmat.primitives.hashes  # noqa E402
import cryptography.hazmat.primitives.serialization  # noqa E402
import cryptography.x509.oid  # noqa E402

from openpaperwork_core.interfaces.app import App  # noqa E402
from openpaperwork_core.interfaces.crypto_certificates import CryptoCertificates  # noqa E402
from openpaperwork_core.interfaces.networking import Networking  # noqa E402
import openpaperwork_core  # noqa E402


LOGGER = logging.getLogger(__name__)


class Plugin(
    openpaperwork_core.PluginBase,
    CryptoCertificates,
):
    @classmethod
    def get_deps(cls):
        return [
            openpaperwork_core.Dependency(
                interface=App,
                defaults=[],
            ),
            openpaperwork_core.Dependency(
                interface=Networking,
                defaults=["openpaperwork_core.networking"],
            ),
        ]

    def crypto_generate_certificate(
            self,
            validity_time_s: int,
            hostnames: Optional[List[str]] = None,
            ip_addresses: Optional[List[str]] = None,
            parent: Optional[Tuple[bytes, bytes]] = None,
            embed_key=False):
        """
        Generate a self-signed certificate.
        """
        (parent_cert, parent_key) = parent if parent is not None else (None, None)

        if parent_cert is not None:
            parent_cert = cryptography.x509.load_pem_x509_certificate(parent_cert)
        if parent_key is not None:
            parent_key = cryptography.hazmat.primitives.serialization.load_pem_private_key(
                parent_key, password=None
            )

        if hostnames is None or len(hostnames) <= 0:
            host_names = self.core.call_success(Networking.networking_get_host_names)
        if ip_addresses is None:
            ip_addresses = self.core.call_success(Networking.networking_get_local_ips)

        LOGGER.info("Generating RSA key ...")
        key = cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=cryptography.hazmat.backends.default_backend(),
        )

        LOGGER.info("Wrapping key in certificate ...")
        name = cryptography.x509.Name([
            cryptography.x509.NameAttribute(
                cryptography.x509.oid.NameOID.COMMON_NAME,
                self.core.call_success(App.app_get_name),
            )
        ])

        now = datetime.datetime.utcnow()
        cert = cryptography.x509.CertificateBuilder()
        cert = cert.subject_name(name)
        cert = cert.issuer_name(
            parent_cert.subject
            if parent_cert is not None
            else name
        )
        cert = cert.public_key(key.public_key())
        cert = cert.serial_number(
            cryptography.x509.random_serial_number(),
        )
        cert = cert.not_valid_before(now)
        cert = cert.not_valid_after(now + datetime.timedelta(seconds=validity_time_s))
        cert = cert.add_extension(
            cryptography.x509.BasicConstraints(
                ca=(True if parent_cert is None else False),
                path_length=(0 if parent_cert is None else None),
            ),
            critical=True,
        )
        cert = cert.add_extension(
            cryptography.x509.SubjectAlternativeName(
                [
                    cryptography.x509.DNSName(str(host))
                    for host in host_names
                ] + [
                    cryptography.x509.IPAddress(ip)
                    for ip in ip_addresses
                ]
            ),
            critical=False
        )

        if parent_cert is None:  # if self-signed / root
            cert = cert.add_extension(
                cryptography.x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
        else:  # if not self-signed
            cert = cert.add_extension(
                cryptography.x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=True,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            cert = cert.add_extension(
                cryptography.x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                    parent_cert.extensions.get_extension_for_class(
                        cryptography.x509.SubjectKeyIdentifier
                    ).value
                ),
                critical=False,
            )
            cert = cert.add_extension(
                cryptography.x509.ExtendedKeyUsage([
                    cryptography.x509.ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=False,
            )
        cert = cert.add_extension(
            cryptography.x509.SubjectKeyIdentifier.from_public_key(
                key.public_key()
            ),
            critical=False,
        )

        LOGGER.info("Signing certificate ...")
        cert = cert.sign(
            parent_key if parent_key is not None else key,
            cryptography.hazmat.primitives.hashes.SHA256(),
            cryptography.hazmat.backends.default_backend()
        )

        LOGGER.info("Exporting certificate and private key ...")
        cert_pem = cert.public_bytes(
            encoding=cryptography.hazmat.primitives.serialization.Encoding.PEM
        )
        key_pem = key.private_bytes(
            encoding=cryptography.hazmat.primitives.serialization.Encoding.PEM,
            format=cryptography.hazmat.primitives.serialization.PrivateFormat.PKCS8,
            encryption_algorithm=cryptography.hazmat.primitives.serialization.NoEncryption(),
        )
        if embed_key:
            cert_pem += key_pem
        LOGGER.info("Certificate and private key generated")

        return (cert_pem, key_pem)

    def crypto_fingerprint_certificate(self, cert: bytes):
        x509 = cryptography.x509.load_pem_x509_certificate(cert)
        return x509.fingerprint(cryptography.hazmat.primitives.hashes.SHA256())
