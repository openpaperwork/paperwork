#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2025 Jerome Flesch
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
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>

import logging
import os


LOGGER = logging.getLogger(__name__)


def rm_rf(path):
    """
    Act as 'rm -rf' in the shell
    """
    if os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for filename in files:
                filepath = os.path.join(root, filename)
                LOGGER.info("Deleting file %s" % filepath)
                os.unlink(filepath)
            for dirname in dirs:
                dirpath = os.path.join(root, dirname)
                if os.path.islink(dirpath):
                    LOGGER.info("Deleting link %s" % dirpath)
                    os.unlink(dirpath)
                else:
                    LOGGER.info("Deleting dir %s" % dirpath)
                    os.rmdir(dirpath)
        LOGGER.info("Deleting dir %s", path)
        os.rmdir(path)


def levenshtein_distance(
            str_a: str, str_b: str,
            str_a_idx: int = 0, str_b_idx: int = 0
        ):
    if str_a_idx == len(str_a) or str_b_idx == len(str_b):
        return len(str_a) - str_a_idx + len(str_b) - str_b_idx

    # no change required
    if str_a[str_a_idx] == str_b[str_b_idx]:
        return levenshtein_distance(str_a, str_b, str_a_idx + 1, str_b_idx + 1)

    return 1 + min(
        # insert character
        levenshtein_distance(str_a, str_b, str_a_idx, str_b_idx + 1),
        # delete character
        levenshtein_distance(str_a, str_b, str_a_idx + 1, str_b_idx),
        # replace character
        levenshtein_distance(str_a, str_b, str_a_idx + 1, str_b_idx + 1),
    )
