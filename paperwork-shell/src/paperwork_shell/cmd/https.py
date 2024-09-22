import time

import openpaperwork_core

from paperwork_shell import _


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['shell']

    def get_deps(self):
        return [
            {
                "interface": "certificate_store",
                "defaults": ["openpaperwork_core.crypto.certificates.store"],
            },
            {
                "interface": "config",
                "defaults": ["openpaperwork_core.config"],
            },
            {
                "interface": "https_backend",
                "defaults": ["paperwork_backend.http"],
            },
            {
                "interface": "networking",
                "defaults": ["openpaperwork_core.networking"],
            },
        ]

    def cmd_complete_argparse(self, parser):
        https_parser = parser.add_parser(
            "https",
            help=_("Manage an HTTPS server to share your work directory with other applications"),
        )

        subparsers = https_parser.add_subparsers(
            help=_("sub-command"), dest="subcommand", required=True,
        )

        subparsers.add_parser(
            "get_server_certificate", help=_("Get public HTTPS server certificate (self-signed)"),
        )
        subparsers.add_parser(
            "get_client_certificate", help=_(
                "Get private certificate for clients (signed with server certificate)"
            ),
        )
        generate_certificates = subparsers.add_parser(
            "generate_certificates", help=_("Generate certificates and keys"),
        )
        generate_certificates.add_argument(
            "-f", "--force", action="store_true",
            help=_("Regenerate even if already existing"),
        )

        subparsers.add_parser(
            "serve", help=_("Start HTTPS server"),
        )

    def _dump(self, console, uri):
        path = self.core.call_success("fs_unsafe", uri)
        console.print(f"File: {path}")
        console.print("")
        with self.core.call_success("fs_open", uri, "r") as fd:
            content = fd.readlines()
        for line in content:
            console.print(line.rstrip())
        return "".join(content)

    def _get_server_certificate(self, console):
        c = self.core.call_success("https_backend_get_server_certificate")
        if c is None:
            console.print("No server certificate")
            return False
        (cert, key) = c
        return self._dump(console, cert)

    def _get_client_certificate(self, console):
        c = self.core.call_success("https_backend_get_client_certificate")
        if c is None:
            console.print("No client certificate")
            return False
        (cert, key) = c
        return self._dump(console, cert)

    def _generate_certificates(self, console, force=False):
        if not force:
            c = self.core.call_success("https_backend_get_server_certificate")
            if c is not None:
                console.print("Certificates and keys already generated")
                return False
        console.print("Regenerating certificates and keys")
        self.core.call_all("https_backend_regenerate_certificates")
        console.print("Certificates and keys regenerated")
        return True

    def _serve(self, console):
        local_ips = self.core.call_success("networking_get_host_names")
        local_ips += self.core.call_success("networking_get_local_ips")

        self.core.call_all("config_put", "https_server", True)

        self.core.call_all("transaction_sync_all")
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.core.call_all("https_backend_reload")

        (cert, key) = self.core.call_success("https_backend_get_server_certificate")
        cert = self.core.call_success("fs_unsafe", cert)
        console.print("Server public certificate:")
        console.print(f"  {cert}")
        (cert, key) = self.core.call_success("https_backend_get_client_certificate")
        cert = self.core.call_success("fs_unsafe", cert)
        console.print("Client public certificate + private key:")
        console.print(f"  {cert}")
        console.print("")

        port = self.core.call_success("config_get", "https_port")
        console.print("Serving on:")
        for local_ip in local_ips:
            console.print(f"    https://{local_ip}:{port}")
        console.print("Ctrl-C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        console.print("Server stopped")
        return True

    def cmd_run(self, console, args):
        if args.command != "https":
            return None
        if args.subcommand == "get_server_certificate":
            return self._get_server_certificate(console)
        elif args.subcommand == "get_client_certificate":
            return self._get_client_certificate(console)
        elif args.subcommand == "generate_certificates":
            return self._generate_certificates(console, args.force)
        elif args.subcommand == "serve":
            return self._serve(console)
