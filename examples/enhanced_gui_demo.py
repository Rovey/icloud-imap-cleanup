#!/usr/bin/env python3
"""
Enhanced GUI Demo for IMAP Mail Cleanup.

This demo showcases the enhanced feedback features including:
- Dual progress bars (overall and phase)
- Real-time statistics
- Processing speed metrics
- Detailed phase information
"""

import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Demo the enhanced GUI functionality."""
    print("IMAP Mail Cleanup - Enhanced GUI Demo")
    print("=" * 50)
    print("Enhanced Features:")
    print("* Dual progress bars (Overall + Current Phase)")
    print("* Real-time email processing counters")
    print("* Processing speed metrics with ETA")
    print("* Detailed phase information")
    print("* Live statistics (Processed/Moved/Skipped)")
    print("* Clean, professional visual feedback")
    print()
    print("The enhanced interface provides detailed feedback while")
    print("maintaining a clean, professional appearance.")
    print()
    print("Starting Enhanced GUI...")

    try:
        from imap_cleanup.gui import IMAPCleanupGUI

        # Create and run the enhanced GUI
        app = IMAPCleanupGUI()
        app.run()

    except ImportError as e:
        print(f"Error: Could not import GUI: {e}")
        print("Make sure you're running from the project directory.")
    except Exception as e:
        print(f"Error running GUI: {e}")

if __name__ == "__main__":
    main()