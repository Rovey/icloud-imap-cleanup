#!/usr/bin/env python3
"""
iCloud IMAP cleaner (safe mode) - Modular Version

This version uses the new modular package structure.
For GUI development, use the imap_cleanup.gui_interface module.

Requirements: Python 3.9+, standard library only.
Usage:
  1) Create an app-specific password at https://appleid.apple.com/
  2) Set env vars IMAP_USER/IMAP_PASS or edit .env file
  3) Adjust settings in config.json as needed
  4) Run: python icloud_imap_cleanup_modular.py
"""

import sys
from imap_cleanup.cli import main

if __name__ == "__main__":
    sys.exit(main())