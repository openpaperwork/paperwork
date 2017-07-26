#!/usr/bin/env python3

import multiprocessing
import sys

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        multiprocessing.freeze_support()

    from paperwork.paperwork import main
    main()