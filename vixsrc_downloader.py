#!/usr/bin/env python3
"""
VixSrc Video Downloader - Wrapper script for backward compatibility

This script maintains backward compatibility with the original single-file interface.
It simply imports and runs the main function from the vixsrc_downloader package.

For the new modular structure, you can also use:
    python -m vixsrc_downloader [arguments]
"""

import sys
from vixsrc_downloader.__main__ import main

if __name__ == '__main__':
    sys.exit(main())
