import abc


class Networking(abc.ABC):
    @abc.abstractmethod
    def networking_get_host_names(self):
        ...

    @abc.abstractmethod
    def networking_get_local_ips(self):
        ...


class NetworkingServiceAnnounce(abc.ABC):
    @abc.abstractmethod
    def networking_announce_service(self, service_name, protocol, port):
        ...

    @abc.abstractmethod
    def networking_unannounce_service(self, service_name, protocol, port):
        ...
