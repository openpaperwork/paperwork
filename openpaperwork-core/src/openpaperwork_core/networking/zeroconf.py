import socket

import zeroconf

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    @classmethod
    def get_interfaces(cls):
        return ["networking_service_announce"]

    @classmethod
    def get_deps(cls):
        return [
            {
                "interface": "networking",
                "defaults": ["openpaperwork_core.networking"],
            },
        ]

    def __init__(self, core):
        super().__init__(core)
        self.service_infos = {}
        self.zeroconf = zeroconf.Zeroconf(ip_version=zeroconf.IPVersion.All)

    def networking_announce_service(self, service_name, protocol, port):
        hostname = socket.gethostname().split(".", 1)[0]

        info = zeroconf.ServiceInfo(
            f"_{protocol}._tcp.local.",
            f"{service_name}._{protocol}._tcp.local.",
            parsed_addresses=[
                str(ip)
                for ip in self.core.call_success("networking_get_local_ips")
            ],
            port=int(port),
            properties={},
            server=f"{hostname}.local.",
        )
        self.service_infos[service_name] = info
        self.zeroconf.register_service(info)

    def networking_unannounce_service(self, service_name, protocol, port):
        info = self.service_infos.pop(service_name)
        self.zeroconf.unregister_service(info)
