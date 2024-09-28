import openpaperwork_core
import openpaperwork_core.promise


class Plugin(openpaperwork_core.PluginBase):
    # Paperwork is designed to be simple to use --> we don't want to be
    # bothered by certificates expiring.
    # If the user wants to revoke their certificates, they can just
    # regenerate them.
    CERTIFICATE_VALIDITY_TIME_S = 100 * 365 * 24 * 3600

    def get_interfaces(self):
        return [
            "certificate_store",
        ]

    def get_deps(self):
        return [
            {
                "interface": "crypto_certificates",
                "defaults": ["openpaperwork_core.crypto.certificates.selfsigned"],
            },
            {
                'interface': 'paths',
                'defaults': ['openpaperwork_core.paths.xdg'],
            },
        ]

    def _get_paths(self, name):
        cert_dir = self.core.call_success("paths_get_config_dir")
        cert_dir = self.core.call_success("fs_join", cert_dir, "paperwork2")
        cert_dir = self.core.call_success("fs_join", cert_dir, "certificates")
        cert_dir = self.core.call_success("fs_resolve", cert_dir)

        self.core.call_success("fs_mkdir_p", cert_dir)
        cert_uri = self.core.call_success("fs_join", cert_dir, f"{name}_certificate.pem")
        cert_uri = self.core.call_success("fs_resolve", cert_uri)
        key_uri = self.core.call_success("fs_join", cert_dir, f"{name}_key.pem")
        key_uri = self.core.call_success("fs_resolve", key_uri)

        if not cert_uri.startswith(cert_dir) or not key_uri.startswith(cert_dir):
            raise Exception(f"Invalid certificate name [{name}]")

        return (cert_uri, key_uri)

    def store_certificate_get(self, name):
        (cert_uri, key_uri) = self._get_paths(name)
        if not self.core.call_success("fs_exists", cert_uri):
            return None
        if not self.core.call_success("fs_exists", key_uri):
            return (cert_uri, None)
        return (cert_uri, key_uri)

    def store_certificate_get_fingerprint(self, name):
        (cert_uri, key_uri) = self._get_paths(name)
        if not self.core.call_success("fs_exists", cert_uri):
            return None
        with self.core.call_success("fs_open", cert_uri, "rb") as fd:
            cert = fd.read()
        return self.core.call_success("crypto_fingerprint_certificate", cert)

    def store_certificate_get_promise(self, name):
        return openpaperwork_core.promise.Promise(
            self.core, self.paperwork_certificate_get,
            args=(name, ),
        )

    def store_certificate_generate(self, name, parent=None, embed_key=False):
        if parent is None:
            parent_key = None
            parent_cert = None
        else:
            (parent_cert_uri, parent_key_uri) = parent
            with self.core.call_success("fs_open", parent_cert_uri, "rb") as fd:
                parent_cert = fd.read()
            with self.core.call_success("fs_open", parent_key_uri, "rb") as fd:
                parent_key = fd.read()

        (cert_pem, key_pem) = self.core.call_success(
            "crypto_generate_certificate",
            self.CERTIFICATE_VALIDITY_TIME_S,
            parent=(parent_cert, parent_key) if parent is not None else None,
            embed_key=embed_key,
        )

        (cert_uri, key_uri) = self._get_paths(name)
        with self.core.call_success("fs_open", cert_uri, "wb") as fd:
            fd.write(cert_pem)
        with self.core.call_success("fs_open", key_uri, "wb") as fd:
            fd.write(key_pem)

        return (cert_uri, key_uri)

    def store_certificate_generate_promise(self, name, parent=None):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.store_certificate_get,
            args=(name, parent),
        )
