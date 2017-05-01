import datetime
import dateutil.parser
import http
import http.client
import json
import logging
import multiprocessing
import os
import platform
import threading
import urllib


logger = logging.getLogger(__name__)


class Beacon(object):
    USER_AGENT = "Paperwork"

    UPDATE_CHECK_INTERVAL = datetime.timedelta(days=7)
    POST_STATISTICS_INTERVAL = datetime.timedelta(days=7)

    GITHUB_RELEASES = {
        'host': 'api.github.com',
        'path': '/repos/openpaperwork/paperwork/releases',
    }
    OPENPAPERWORK_RELEASES = {
        'host': 'openpaper.work',
        'path': '/beacon/latest',
    }
    OPENPAPERWORK_STATS = {
        'host': 'openpaper.work',
        'path': '/beacon/post_statistics',
    }

    def __init__(self, config):
        super().__init__()
        self.config = config

    def get_version_github(self):
        logger.info("Querying GitHub ...")
        h = http.client.HTTPSConnection(
            host=self.GITHUB_RELEASES['host'],
        )
        h.request('GET', url=self.GITHUB_RELEASES['path'], headers={
            'User-Agent': self.USER_AGENT
        })
        r = h.getresponse()
        r = r.read().decode('utf-8')
        r = json.loads(r)

        last_tag_date = None
        last_tag_name = None
        for release in r:
            date = dateutil.parser.parse(release['created_at'])
            tag = release['tag_name']
            if last_tag_date is None or last_tag_date < date:
                last_tag_date = date
                last_tag_name = tag
        return last_tag_name

    def get_version_openpaperwork(self):
        logger.info("Querying OpenPaper.work ...")
        h = http.client.HTTPSConnection(
            host=self.OPENPAPERWORK_RELEASES['host'],
        )
        h.request('GET', url=self.OPENPAPERWORK_RELEASES['path'], headers={
            'User-Agent': self.USER_AGENT
        })
        r = h.getresponse()
        r = r.read().decode('utf-8')
        r = json.loads(r)
        return r['paperwork'][os.name]

    def check_update(self):
        if not self.config['check_for_update'].value:
            logger.info("Update checking is disabled")
            return

        now = datetime.datetime.now()
        last_check = self.config['last_update_check'].value

        logger.info("Updates were last checked: {}".format(last_check))
        if (last_check is not None and
                last_check + self.UPDATE_CHECK_INTERVAL >= now):
            logger.info("No need to check for new updates yet")
            return

        logger.info("Checking for updates ...")
        version = None
        try:
            version = self.get_version_github()
        except Exception as exc:
            logger.exception(
                "Failed to get latest Paperwork release from GitHub. "
                "Falling back on openpaper.work ...",
                exc_info=exc
            )
        if version is None:
            try:
                version = self.get_version_openpaperwork()
            except Exception as exc:
                logger.exception(
                    "Failed to get latest Paperwork from Openpaper.work",
                    exc_info=exc
                )
        if version is None:
            return

        logger.info("Latest Paperwork release: {}".format(version))
        self.config['last_update_found'].value = version
        self.config['last_update_check'].value = now
        self.config.write()

    def get_statistics(self, version, docsearch):
        distribution = platform.linux_distribution()
        if distribution[0] == '':
            distribution = platform.win32_ver()
        processor = ""
        if os.name != 'nt':  # contains too much infos on Windows
            processor = platform.processor()
        return {
            'uuid': int(self.config['uuid'].value),
            'paperwork_version': str(version),
            'nb_documents': int(docsearch.nb_docs),
            'os_name': str(os.name),
            'platform_architecture': str(platform.architecture()),
            'platform_processor': str(processor),
            'platform_distribution': str(distribution),
            'cpu_count': int(multiprocessing.cpu_count()),
        }

    def send_statistics(self, version, docsearch):
        if not self.config['send_statistics'].value:
            logger.info("Anonymous statistics are disabled")
            return

        now = datetime.datetime.now()
        last_post = self.config['last_statistics_post'].value

        logger.info("Statistics were last posted: {}".format(last_post))
        if (last_post is not None and
                last_post + self.POST_STATISTICS_INTERVAL >= now):
            logger.info("No need to post statistics")
            return

        logger.info("Sending anonymous statistics ...")
        stats = self.get_statistics(version, docsearch)
        logger.info("Statistics: {}".format(stats))

        logger.info("Posting statistics on openpaper.work ...")
        h = http.client.HTTPSConnection(
            host=self.OPENPAPERWORK_STATS['host'],
        )
        h.request('POST', url=self.OPENPAPERWORK_STATS['path'], headers={
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
            'User-Agent': self.USER_AGENT,
        }, body=urllib.parse.urlencode({
            'statistics': json.dumps(stats),
        }))
        r = h.getresponse()
        logger.info("Getting reply from openpaper.work ({})".format(r.status))
        reply = r.read().decode('utf-8')
        if r.status == http.client.OK:
            logger.info("Openpaper.work replied: {} | {}".format(
                r.status, r.reason
            ))
        else:
            logger.warning("Openpaper.work replied: {} | {}".format(
                r.status, r.reason
            ))
            logger.warning("Openpaper.work: {}".format(reply))

        self.config['last_statistics_post'].value = now
        self.config.write()


def check_update(beacon):
    thread = threading.Thread(target=beacon.check_update)
    thread.start()


def send_statistics(beacon, version, docsearch):
    thread = threading.Thread(target=beacon.send_statistics, kwargs={
        'version': version,
        'docsearch': docsearch,
    })
    thread.start()
