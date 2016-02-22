#!/usr/bin/env python3

#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
#    Copyright (C) 2012  Sebastien Maccagnoni-Munch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
from paperwork_backend import config
from paperwork_backend.docsearch import DocSearch
from http.server import HTTPServer, SimpleHTTPRequestHandler
import logging
import json

logger = logging.getLogger(__name__)
pconfig = None
searchdoc = None

#
# Request handler
#


class WebHandler(SimpleHTTPRequestHandler):
    def _send_response(self, mimetype, binary=False, absPath=False):
        try:
            self.send_response(200)
            self.send_header("Content-Type", mimetype)
            self.end_headers()
            print(binary)
            if bool(binary):
                if absPath:
                    f = open(self.path, "rb")
                else:
                    f = open(os.path.dirname(os.path.abspath(__file__)) +
                             self.path.split("?")[0], "rb")
                self.wfile.write(f.read())
                f.close()
            else:
                f = open(os.path.dirname(os.path.abspath(__file__)) +
                         self.path.split("?")[0])
                self.wfile.write(bytes(f.read(), "utf-8"))
                f.close()
        except IOError:
            self.send_error(404, "File Not Found:" + self.path)

    def _get_search_suggestions(self, term):
        global searchdoc
        logger.info(type(term))
        suggestions = searchdoc.find_documents(term)
        self.send_response(200)
        self.send_header("Content-Type", "text/json")
        self.end_headers()
        self.wfile.write(bytes(json.dumps(
                                {'files':
                                    [{'name': s.name, 'id': s.id}
                                        for s in suggestions]}),
                               "utf-8"))

    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-Type", "text/html")
        s.end_headers()

    def do_GET(s):
        global searchdoc
        print(len(s.path.split('?')))
        if s.path == "/":
            s.path = "/pages/index.html"

        if s.path.split('?')[0].replace("/", "") == "search":
            logger.info("Send suggestion")
            s._get_search_suggestions(
                s.path.split('?')[1].replace("term=", ""))
        elif not s.path.split('?')[0].endswith("viewer.html") and \
                s.path.split('?')[0].endswith("doc.pdf"):
            s.path = searchdoc.rootdir + os.sep + \
                s.path.replace("/pages/web/", "")
            s._send_response("application/pdf", True, True)
        elif s.path.split('?')[0].endswith(".html"):
            s._send_response("text/html")
        elif s.path.endswith(".css"):
            s._send_response("text/css")
        elif s.path.endswith(".js"):
            s._send_response("application/javascript")
        elif s.path.endswith(".png"):
            s._send_response("image/png", True)
        elif s.path.endswith(".gif"):
            s._send_response("image/gif", True)
        elif s.path.endswith(".properties"):
            s._send_response("text/plain")
        elif s.path.split('?')[0].endswith(".pdf"):
            s._send_response("application/pdf", True)
        elif s.path.endswith(".ico"):
            s._send_response("image/x-icon", True)


def main():
    global searchdoc
    formatter = logging.Formatter(
        '%(levelname)-6s %(name)-30s %(message)s')
    handler = logging.StreamHandler()
    logger = logging.getLogger()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel({
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }[os.getenv("PAPERWORK_VERBOSE", "INFO")])

    pconfig = config.PaperworkConfig()
    pconfig.read()
    logger.info("Read config...")

    logger.info("Creating DocSearch opject")
    searchdoc = DocSearch(pconfig.settings['workdir'].value)
    print(searchdoc.rootdir)
    logger.info("DocSearch object created")

    logger.info("WebServer starting...")

    ServerClass = HTTPServer
    httpd = ServerClass(('', 8001), WebHandler)
    try:
        httpd.serve_forever()
        logger.info("WebServer running!")
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logger.info("WebServer stopped!")
