#!/usr/bin/env python

import os.path


def is_tmp_file(filepath):
    if not os.path.isfile(filepath):
        return False
    basename = os.path.basename(filepath)
    return basename.startswith(page.ImgPage.ROTATED_FILE_PREFIX)
