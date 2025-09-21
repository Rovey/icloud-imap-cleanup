#!/usr/bin/env python3
"""
GUI Demo for IMAP Mail Cleanup.

This demo shows how to launch the GUI without actually connecting to email.
"""

import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Demo the GUI functionality."""
    print("IMAP Mail Cleanup - GUI Demo")
    print("=" * 40)
    print("This demo shows the GUI interface.")
    print("You can edit configuration, test connections, and see the interface.")
    print("Note: You'll need valid IMAP credentials to actually process emails.")
    print()
    print("Starting GUI...")

    try:
        from imap_cleanup.gui import IMAPCleanupGUI

        # Create and run the GUI
        app = IMAPCleanupGUI()
        app.run()

    except ImportError as e:
        print(f"Error: Could not import GUI: {e}")
        print("Make sure you're running from the project directory.")
    except Exception as e:
        print(f"Error running GUI: {e}")

if __name__ == "__main__":
    main()