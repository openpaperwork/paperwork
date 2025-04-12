import ifaddr
import ipaddress
import socket

from openpaperwork_core.interfaces.networking import Networking
import openpaperwork_core


class Plugin(
    openpaperwork_core.PluginBase,
    Networking
):
    def networking_get_host_names(self):
        return [
            socket.gethostname(),
            socket.getfqdn(),
            f"{socket.gethostname().split('.')[0]}.local",
        ]

    def networking_get_local_ips(self):
        ips = [
            ip.ip if not isinstance(ip.ip, tuple) else ip.ip[0]
            for adapter in ifaddr.get_adapters()
            for ip in adapter.ips
        ]
        ips = [ipaddress.ip_address(ip) for ip in ips]
        ips = [
            ip for ip in ips
            if (
                (ip.is_private or ip.is_global)
                and not ip.is_loopback
                and not ip.is_link_local
            )
        ]
        return ips
