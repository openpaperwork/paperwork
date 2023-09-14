"""
module 'http' contains all the code to communicate using HTTP+JSON with
https://www.openpaper.work/:
- update notification
- anonymous statistics
- etc
"""
import base64
import http
import http.client
import json
import logging
import os
import ssl
import urllib

from . import PluginBase
from . import promise


if os.name == "nt":
    import certifi


LOGGER = logging.getLogger(__name__)
DEFAULT_SERVER = "www.openpaper.work"
DEFAULT_PROTOCOL = "https"


class JsonHttp(object):
    def __init__(self, core, module_name):
        self.core = core
        self.user_agent = "{} {}".format(
            core.call_success("app_get_name"),
            core.call_success("app_get_version")
        )
        self.config_section_name = module_name

        settings = {
            self.config_section_name + "_protocol":
                core.call_success(
                    "config_build_simple", self.config_section_name,
                    "protocol", lambda: DEFAULT_PROTOCOL
                ),
            self.config_section_name + "_server":
                core.call_success(
                    "config_build_simple", self.config_section_name,
                    "server", lambda: DEFAULT_SERVER
                ),
        }
        for (k, setting) in settings.items():
            core.call_all("config_register", k, setting)

    def _convert(self, data):
        if isinstance(data, str):
            return data
        if isinstance(data, bytes):
            return base64.encodebytes(data).decode("utf-8").strip()
        return json.dumps(data)

    def _request(self, data, protocol, server, path):
        if protocol == "http":
            h = http.client.HTTPConnection(host=server)
        elif os.name == "nt":
            # On Windows, when frozen, we must specify a cafile
            cafile = certifi.where()
            ssl_context = ssl.create_default_context(cafile=cafile)
            h = http.client.HTTPSConnection(host=server, context=ssl_context)
        else:
            h = http.client.HTTPSConnection(host=server)

        if data is None or (isinstance(data, str) and data == ""):
            LOGGER.info("Sending GET %s/%s", server, path)
            h.request('GET', url=path, headers={'User-Agent': self.user_agent})
        else:
            body = urllib.parse.urlencode({
                k: self._convert(v)
                for (k, v) in data.items()
            })
            LOGGER.info("Sending POST %s/%s", server, path)
            h.request(
                'POST', url=path, headers={
                    "Content-type": "application/x-www-form-urlencoded",
                    "Accept": "text/plain",
                    'User-Agent': self.user_agent,
                },
                body=body
            )
        r = h.getresponse()
        reply = r.read().decode('utf-8')
        LOGGER.info("Got HTTP %s: %s - %s", r.status, r, reply)
        if r.status != http.client.OK:
            raise ConnectionError("HTTP {}: {} - {}".format(
                r.status, r, reply
            ))
        if reply[0] != '[' and reply[0] != '{':
            return reply
        return json.loads(reply)

    def get_request_promise(self, path):
        protocol = self.core.call_success(
            "config_get", self.config_section_name + "_protocol"
        )
        server = self.core.call_success(
            "config_get", self.config_section_name + "_server"
        )

        return promise.ThreadedPromise(
            self.core, self._request, args=(protocol, server, path)
        )


class Plugin(PluginBase):
    def get_interfaces(self):
        return ['http_json']

    def get_deps(self):
        return [
            {
                'interface': 'app',
                'defaults': ['openpaperwork_core.app'],
            },
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
        ]

    def http_json_get_client(self, module_name):
        return JsonHttp(self.core, module_name)
