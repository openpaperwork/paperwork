import os
import unittest

os.environ["CRYPTOGRAPHY_OPENSSL_NO_LEGACY"] = "1"

import cryptography.x509  # noqa E402
import cryptography.x509.verification  # noqa E402

import openpaperwork_core  # noqa E402



class FakeAppModule:
    class Plugin(openpaperwork_core.PluginBase):
        def get_interfaces(self):
            return [
                "app",
            ]

        def app_get_name(self):
            return "testapp.com"


class TestSelfSigned(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core._load_module("fake_app_module", FakeAppModule())
        self.core.load("openpaperwork_core.crypto.certificates.selfsigned")
        self.core.init()

    def test_generate(self):
        (cert_pem, key_pem) = self.core.call_success(
            "crypto_generate_certificate", validity_time_s=(365 * 24 * 3600)
        )
        self.assertTrue(isinstance(cert_pem, bytes))
        self.assertTrue(isinstance(key_pem, bytes))

    def test_generate_child(self):
        (parent_cert_pem, parent_key_pem) = self.core.call_success(
            "crypto_generate_certificate", validity_time_s=(365 * 24 * 3600)
        )
        self.assertTrue(isinstance(parent_cert_pem, bytes))
        self.assertTrue(isinstance(parent_key_pem, bytes))

        (child_cert_pem, child_key_pem) = self.core.call_success(
            "crypto_generate_certificate",
            validity_time_s=(365 * 24 * 3600),
            parent=(parent_cert_pem, parent_key_pem)
        )
        self.assertTrue(isinstance(child_cert_pem, bytes))
        self.assertTrue(isinstance(child_key_pem, bytes))

        parent_cert = cryptography.x509.load_pem_x509_certificate(parent_cert_pem)
        child_cert = cryptography.x509.load_pem_x509_certificate(child_cert_pem)

        store = cryptography.x509.verification.Store([parent_cert])
        builder = cryptography.x509.verification.PolicyBuilder().store(store)
        verifier = builder.build_client_verifier()
        chain = verifier.verify(child_cert, [])
        self.assertIsNotNone(chain)
