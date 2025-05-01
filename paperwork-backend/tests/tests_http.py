import http
import http.client
import tempfile
import shutil
import ssl
import unittest

from openpaperwork_core.interfaces.app import App
from openpaperwork_core.interfaces.certificate_store import CertificateStore
from openpaperwork_core.interfaces.config import Config
from openpaperwork_core.interfaces.fs import Fs
from openpaperwork_core.interfaces.quit import QuitListener
import openpaperwork_core
import openpaperwork_core.util

from paperwork_backend.interfaces.http import HttpsBackend
import paperwork_backend.http


class FakeModule:
    __name__ = "fake_module"

    class Plugin(
        openpaperwork_core.PluginBase,
        App,
    ):
        def app_get_name(self):
            return "testapp.com"

        def app_get_fs_name(self):
            pass

        def app_get_version(self):
            pass


class TestHttpsWorkdir(unittest.TestCase):
    def setUp(self):
        openpaperwork_core.util.reset_singletons()

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("fake_module", FakeModule())
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model.extra_text")
        self.core.load("paperwork_backend.model")
        self.core.load("paperwork_backend.model.hocr")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.img_overlay")
        self.core.load("paperwork_backend.model.pdf")
        self.core.load("paperwork_backend.model.workdir")
        self.core.load("paperwork_backend.http")
        self.core.load("paperwork_backend.http.workdir")
        self.core.init()

        self.work_dir = tempfile.mkdtemp(prefix="paperwork_tests_all_")
        self.work_dir_url = self.core.call_success(Fs.fs_safe, self.work_dir)
        self.core.call_all(Config.config_put, "workdir", self.work_dir_url)
        self.core.call_all(Config.config_put, "https_server", True)

        self.doc_pdf = self.core.call_success(
            Fs.fs_join, self.work_dir_url, "20200525_1241_05"
        )
        self._make_file(self.doc_pdf + "/paper.2.words")

    def tearDown(self):
        self.core.call_all(QuitListener.on_quit)
        shutil.rmtree(self.work_dir)

    def _make_file(self, out_file_url):
        dirname = self.core.call_success(Fs.fs_dirname, out_file_url)
        self.core.call_success(Fs.fs_mkdir_p, dirname)
        with self.core.call_success(Fs.fs_open, out_file_url, 'w') as fd:
            fd.write("Generated content\n")

    def _make_https_query(self, verb, path):
        client_cert = self.core.call_success(
            CertificateStore.store_certificate_get,
            paperwork_backend.http.CLIENT_CERT_NAME,
        )
        ssl_context = ssl._create_unverified_context()
        ssl_context.load_cert_chain(
            self.core.call_success(Fs.fs_unsafe, client_cert[0]),
            keyfile=self.core.call_success(Fs.fs_unsafe, client_cert[1]),
        )
        h = http.client.HTTPSConnection(
            host="127.0.0.1",
            port=self.core.call_success(Config.config_get, "https_port"),
            context=ssl_context,
        )
        try:
            h.request(verb, url=path)
            r = h.getresponse()
            return r.status
        finally:
            h.close()

    def test_http(self):
        self.core.call_all(HttpsBackend.https_backend_reload)
        r = self._make_https_query(
            "GET",
            "/papers/20200525_1241_05/paper.2.words"
        )
        self.assertEqual(r, 200)

        r = self._make_https_query(
            "GET",
            "/papers/20200525_1241_05/doc.pdf"
        )
        self.assertEqual(r, 404)
