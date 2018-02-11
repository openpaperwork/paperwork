#!/usr/bin/env python

import glob
import logging
import os

from . import _version
from . import util

logger = logging.getLogger(__name__)


def init_flatpak():
    """
    If we are in Flatpak, we must build a tessdata/ directory using the
    .traineddata files from each locale directory
    """
    tessdata_files = glob.glob("/app/share/locale/*/*.traineddata")
    if len(tessdata_files) <= 0:
        return os.path.exists("/app")

    localdir = os.path.expanduser("~/.local")
    base_data_dir = os.getenv(
        "XDG_DATA_HOME",
        os.path.join(localdir, "share")
    )
    tessdatadir = os.path.join(base_data_dir, "paperwork", "tessdata")

    logger.info("Assuming we are running in Flatpak."
                " Building tessdata directory {} ...".format(tessdatadir))
    util.rm_rf(tessdatadir)
    util.mkdir_p(tessdatadir)

    os.symlink("/app/share/tessdata/eng.traineddata",
               os.path.join(tessdatadir, "eng.traineddata"))
    os.symlink("/app/share/tessdata/osd.traineddata",
               os.path.join(tessdatadir, "osd.traineddata"))
    os.symlink("/app/share/tessdata/configs",
               os.path.join(tessdatadir, "configs"))
    os.symlink("/app/share/tessdata/tessconfigs",
               os.path.join(tessdatadir, "tessconfigs"))
    for tessdata in tessdata_files:
        logger.info("{} found".format(tessdata))
        os.symlink(tessdata, os.path.join(tessdatadir,
                                          os.path.basename(tessdata)))
    os.environ['TESSDATA_PREFIX'] = os.path.dirname(tessdatadir)
    logger.info("Tessdata directory ready")
    return True


def init():
    state = {
        "flatpak": False,
    }
    state['flatpak'] = init_flatpak()
    return state


__version__ = _version.version
