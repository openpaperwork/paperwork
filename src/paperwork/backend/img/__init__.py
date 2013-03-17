#!/usr/bin/env python

import os.path

def is_tmp_file(filepath):
    if not os.path.isfile(filepath):
        return False
    return os.path.basename(filepath).startswith(page.ImgPage.ROTATED_FILE_PREFIX)
