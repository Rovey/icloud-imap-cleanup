#!/usr/bin/env python3
"""
IMAP Mail Cleanup - GUI Application

Launch the graphical user interface for email cleanup with configuration editing,
progress tracking, and real-time feedback.

Requirements: Python 3.9+, tkinter (included with Python)
Usage: python imap_cleanup_gui.py
"""

import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from imap_cleanup.gui import main
except ImportError as e:
    print(f"Error: Could not import GUI module: {e}")
    print("Make sure you're running this from the project directory.")
    sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGUI application interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)