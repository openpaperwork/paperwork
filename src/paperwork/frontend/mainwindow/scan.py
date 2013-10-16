import logging
import multiprocessing
import re
import threading
import time

from gi.repository import GLib
from gi.repository import GObject
import pyocr
import pyocr.builders

from paperwork.backend.util import check_spelling
from paperwork.frontend.util.jobs import Job
from paperwork.frontend.util.jobs import JobFactory
from paperwork.frontend.util.canvas.drawers import Drawer


logger = logging.getLogger(__name__)


class JobScan(Job):
    __gsignals__ = {
        'scan-started': (GObject.SignalFlags.RUN_LAST, None, ()),
        'scan-info': (GObject.SignalFlags.RUN_LAST, None,
                      (
                          # expected width
                          GObject.TYPE_INT,
                          # expected height
                          GObject.TYPE_INT,
                      )),
        'scan-chunk': (GObject.SignalFlags.RUN_LAST, None,
                       # line where to put the image
                       (GObject.TYPE_INT,
                        GObject.TYPE_PYOBJECT,)),  # The PIL image
        'scan-done': (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_PYOBJECT,  # Pillow image
                      )),
        'scan-canceled': (GObject.SignalFlags.RUN_LAST, None,
                          ()),
    }

    can_stop = True
    priority = 10

    def __init__(self, factory, id, scan_session):
        Job.__init__(self, factory, id)
        self.can_run = False
        self.scan_session = scan_session

    def do(self):
        self.can_run = True
        logger.info("Scan started")
        self.emit('scan-started')

        size = self.scan_session.scan.expected_size
        self.emit('scan-info', size[0], size[1])

        last_line = 0
        try:
            while self.can_run:
                self.scan_session.scan.read()

                next_line = self.scan_session.scan.available_lines[1]
                if (next_line > last_line):
                    chunk = self.scan_session.scan.get_image(last_line, next_line)
                    self.emit('scan-chunk', last_line, chunk)
                    last_line = next_line

                time.sleep(0)  # Give some CPU time to PyGtk
            if not self.can_run:
                logger.info("Scan canceled")
                self.emit('scan-canceled')
                return
        except EOFError:
            pass

        img = self.scan_session.images[-1]
        self.emit('scan-done', img)
        logger.info("Scan done")

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()
        if not will_resume:
            self.scan_session.scan.cancel()


GObject.type_register(JobScan)


class JobFactoryScan(JobFactory):
    def __init__(self, scan_scene):
        JobFactory.__init__(self, "Scan")
        self.scan_scene = scan_scene

    def make(self, scan_session):
        job = JobScan(self, next(self.id_generator), scan_session)
        job.connect("scan-started",
                    lambda job: GLib.idle_add(self.scan_scene.on_scan_start))
        job.connect("scan-info",
                    lambda job, x, y:
                    GLib.idle_add(self.scan_scene.on_scan_info, x, y))
        job.connect("scan-chunk",
                    lambda job, line, img_chunk:
                    GLib.idle_add(self.scan_scene.on_scan_chunk, line,
                                  img_chunk))
        job.connect("scan-done",
                    lambda job, img: GLib.idle_add(self.scan_scene.on_scan_done,
                                                   img))
        job.connect("scan-canceled", lambda job:
                    GLib.idle_add(self.scan_scene.on_scan_canceled))
        return job


class _ImgOCRThread(threading.Thread):
    # we don't use jobs here, because we would need 1 scheduler for each job
    # --> too painful and useless

    def __init__(self, name, ocr_tool, langs, angle, img):
        threading.Thread.__init__(self, name="OCR")
        self.name = name
        self.ocr_tool = ocr_tool
        self.langs = langs
        self.angle = angle
        self.img = img
        self.score = -1
        self.boxes = None

    def __compute_ocr_score_with_spell_checking(self, txt):
        return check_spelling(self.langs['spelling'], txt)

    @staticmethod
    def __boxes_to_txt(boxes):
        txt = u""
        for line in boxes:
            txt += line.content + u"\n"
        return txt

    @staticmethod
    def __compute_ocr_score_without_spell_checking(txt):
        """
        Try to evaluate how well the OCR worked.
        Current implementation:
            The score is the number of words only made of 4 or more letters
            ([a-zA-Z])
        """
        # TODO(Jflesch): i18n / l10n
        score = 0
        prog = re.compile(r'^[a-zA-Z]{4,}$')
        for word in txt.split(" "):
            if prog.match(word):
                score += 1
        return (txt, score)

    def run(self):
        SCORE_METHODS = [
            ("spell_checker", self.__compute_ocr_score_with_spell_checking),
            ("lucky_guess", self.__compute_ocr_score_without_spell_checking),
            ("no_score", lambda txt: (txt, 0))
        ]

        logger.info("Running OCR on page orientation %s" % self.name)
        self.boxes = self.ocr_tool.image_to_string(
            self.img, lang=self.langs['ocr'],
            builder=pyocr.builders.LineBoxBuilder())

        txt = self.__boxes_to_txt(self.boxes)

        for score_method in SCORE_METHODS:
            try:
                logger.info("Evaluating score of page orientation (%s)"
                             " using method '%s' ..."
                             % (self.name, score_method[0]))
                (_, self.score) = score_method[1](txt)
                # TODO(Jflesch): For now, we throw away the fixed version of the
                # text:
                # The original version may contain proper nouns, and spell
                # checking could make them disappear
                # However, it would be best if we could keep both versions
                # without increasing too much indexation time
                return
            except Exception, exc:
                logger.error("Scoring method '%s' on orientation %s failed !"
                             % (score_method[0], self.name))
                logger.error("Reason: %s" % exc)


class JobOCR(Job):
    __gsignals__ = {
        'ocr-started': (GObject.SignalFlags.RUN_LAST, None,
                        (GObject.TYPE_PYOBJECT,  # image to ocr
                        )),
        'ocr-angles': (GObject.SignalFlags.RUN_LAST, None,
                       # list of images to ocr: { angle: img }
                       (GObject.TYPE_PYOBJECT,
                       )),
        'ocr-score': (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_INT,  # angle
                       GObject.TYPE_FLOAT,  # score
                      )),
        'ocr-done': (GObject.SignalFlags.RUN_LAST, None,
                     (GObject.TYPE_INT,   # angle
                      GObject.TYPE_PYOBJECT,  # image to ocr (rotated)
                      GObject.TYPE_PYOBJECT,  # line + word boxes
                     )),
    }

    can_stop = False
    priority = 5

    OCR_THREADS_POLLING_TIME = 0.1

    def __init__(self, factory, id,
                 ocr_tool, langs, angles, img):
        Job.__init__(self, factory, id)
        self.ocr_tool = ocr_tool
        self.langs = langs
        self.angles = angles
        self.img = img

    def do(self):
        self.emit('ocr-started', self.img)
        imgs = {angle: self.img.rotate(angle) for angle in self.angles}
        self.emit('ocr-angles', imgs)

        max_threads = multiprocessing.cpu_count()
        threads = []
        scores = []

        if len(imgs) > 1:
            logger.debug("Will use %d process(es) for OCR" % (max_threads))

        # Run the OCR tools in as many threads as there are processors/core
        # on the computer
        nb = 0
        while (len(imgs) > 0 or len(threads) > 0):
            # look for finished threads
            for thread in threads:
                if not thread.is_alive():
                    threads.remove(thread)
                    logger.info("OCR done on angle %d: %f"
                                % (thread.angle, thread.score))
                    scores.append((thread.score, thread.angle,
                                   thread.img, thread.boxes))
                    self.emit('ocr-score', thread.angle, thread.score)
            # start new threads if required
            while (len(threads) < max_threads and len(imgs) > 0):
                (angle, img) = imgs.popitem()
                logger.info("Starting OCR on angle %d" % angle)
                thread = _ImgOCRThread(str(nb), self.ocr_tool,
                                       self.langs, angle, img)
                thread.start()
                threads.append(thread)
                nb += 1
            time.sleep(self.OCR_THREADS_POLLING_TIME)

        # We want the higher score first
        scores.sort(cmp=lambda x, y: cmp(y[0], x[0]))

        logger.info("Best: %f" % (scores[0][0]))

        self.emit('ocr-done', scores[0][1], scores[0][2], scores[0][3])


GObject.type_register(JobOCR)


class JobFactoryOCR(JobFactory):
    def __init__(self, scan_scene, config):
        JobFactory.__init__(self, "OCR")
        self.__config = config
        self.scan_scene = scan_scene

    def make(self, img):
        angles = range(0, self.__config.ocr_nb_angles * 90, 90)

        ocr_tools = pyocr.get_available_tools()
        if len(ocr_tools) == 0:
            print("No OCR tool found")
            sys.exit(1)
        ocr_tool = ocr_tools[0]
        print("Will use tool '%s'" % (ocr_tool.get_name()))

        job = JobOCR(self, next(self.id_generator), ocr_tool,
                     self.__config.langs, angles, img)
        job.connect("ocr-started", lambda job, img:
                    GLib.idle_add(self.scan_scene.on_ocr_started, img))
        job.connect("ocr-angles", lambda job, imgs:
                    GLib.idle_add(self.scan_scene.on_ocr_angles, imgs))
        job.connect("ocr-score", lambda job, angle, score:
                    GLib.idle_add(self.scan_scene.on_ocr_score, angle, score))
        job.connect("ocr-done", lambda job, angle, img, boxes:
                    GLib.idle_add(self.scan_scene.on_ocr_done, angle, img,
                                  boxes))
        return job


class ScanSceneDrawer(Drawer):
    def __init__(self, scan_scene):
        Drawer.__init__(self)
        self.scan_scene = scan_scene
        # TODO


class ScanScene(GObject.GObject):
    __gsignals__ = {
        'scan-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'scan-done': (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_PYOBJECT,  # PIL image
                      )),
        'ocr-start': (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_PYOBJECT,  # PIL image
                      )),
        'ocr-done': (GObject.SignalFlags.RUN_LAST, None,
                     (GObject.TYPE_PYOBJECT,  # PIL image
                      GObject.TYPE_PYOBJECT,  # line + word boxes
                     )),
    }

    STEP_SCAN = 0
    STEP_OCR = 1

    def __init__(self, config, scan_scheduler, ocr_scheduler):
        GObject.GObject.__init__(self)
        self.config = config
        self.schedulers = {
            'scan': scan_scheduler,
            'ocr': ocr_scheduler,
        }

        self.current_step = -1
        self.drawer = ScanSceneDrawer(self)

        self.factories = {
            'scan': JobFactoryScan(self),
            'ocr': JobFactoryOCR(self, config),
        }

    def scan(self, scan_session):
        """
        Returns immediately
        Listen for the signal scan-scene-scan-done to get the result
        """
        job = self.factories['scan'].make(scan_session)
        self.schedulers['scan'].schedule(job)


    def on_scan_start(self):
        # TODO
        self.emit('scan-start')

    def on_scan_info(self, img_x, img_y):
        pass

    def on_scan_chunk(self, line, img_chunk):
        pass

    def on_scan_done(self, img):
        # TODO
        self.emit('scan-done', img)

    def on_scan_canceled(self):
        # TODO
        self.emit('scan-done', None)

    def ocr(self, img):
        """
        Returns immediately.
        Listen for the signal scan-scene-ocr-done to get the result
        """
        job = self.factories['ocr'].make(img)
        self.schedulers['ocr'].schedule(job)

    def on_ocr_started(self, img):
        # TODO
        self.emit('ocr-start', img)

    def on_ocr_angles(self, imgs):
        pass

    def on_ocr_score(self, angle, score):
        pass

    def on_ocr_done(self, angle, img, boxes):
        # TODO
        self.emit('ocr-done', img, boxes)

    def scan_and_ocr(self, scan_session):
        """
        Convenience function.
        Returns immediately.
        """
        class _ScanOcrChainer(object):
            def __init__(self, scan_scene):
                scan_scene.connect("scan-done", self.__start_ocr)

            def __start_ocr(self, scan_scene, img):
                if img is None:
                    return
                scan_scene.ocr(img)

        _ScanOcrChainer(self)
        self.scan(scan_session)


GObject.type_register(ScanScene)
