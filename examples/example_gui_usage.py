#!/usr/bin/env python3
"""
Example of how to use the GUI interface for building a GUI application.

This demonstrates how to integrate the email processing with any GUI framework.
"""

from imap_cleanup.gui_interface import GUIInterface, ProcessingCallback


class ExampleCallback(ProcessingCallback):
    """Example callback implementation for console output."""

    def on_start(self, stats):
        print(f"🚀 Starting processing with {stats['max_workers']} workers")
        print(f"   CPU cores: {stats['cpu_cores']}, Connections: {stats['total_connections']}")

    def on_folder_start(self, folder, total_folders, current_folder):
        print(f"📁 Processing folder {current_folder}/{total_folders}: {folder}")

    def on_phase_start(self, phase, total_items):
        print(f"⚡ Phase: {phase} ({total_items} items)")

    def on_progress(self, current, total, message=""):
        progress = (current / total * 100) if total > 0 else 0
        print(f"   Progress: {current}/{total} ({progress:.1f}%) {message}")

    def on_email_processed(self, action, uid, from_addr, subject, reason):
        if action == "moved":
            print(f"   ✅ Moved: {from_addr} | {reason}")
        elif action == "skip":
            print(f"   ⏭️  Skip: {from_addr} | {reason}")

    def on_folder_complete(self, folder, candidates, moved):
        print(f"✅ Folder {folder} complete: {candidates} candidates, {moved} moved")

    def on_complete(self, total_candidates, total_moved):
        print(f"🎉 Processing complete: {total_candidates} candidates, {total_moved} moved")

    def on_error(self, error, details=""):
        print(f"❌ Error: {error}")
        if details:
            print(f"   Details: {details}")


def main():
    """Example GUI usage."""
    print("IMAP Mail Cleanup - GUI Interface Example")
    print("=" * 50)

    # Initialize GUI interface
    gui = GUIInterface()

    # Get configuration
    config = gui.get_config()
    print(f"Current mode: {'DRY RUN' if config['cleanup_settings']['dry_run'] else 'LIVE'}")

    # Get processing stats
    stats = gui.get_processing_stats()
    print(f"Workers: {stats['max_workers']} + {stats['header_fetch_workers']} header fetch")
    print(f"Batch size: {stats['batch_size']}")

    # Test connection
    success, message = gui.test_connection()
    print(f"Connection test: {'✅ ' + message if success else '❌ ' + message}")

    if not success:
        return

    # Example: Update configuration
    gui.update_config({
        "cleanup_settings": {
            "verbose": True,
            "dry_run": True  # Keep in dry run for example
        }
    })

    # Start processing with callback
    callback = ExampleCallback()

    print("\n🚀 Starting email processing...")
    if gui.start_processing(callback):
        print("Processing started in background thread")

        # In a real GUI, you would update the interface here
        # For this example, we'll just wait
        import time
        while gui.is_processing():
            time.sleep(1)

        print("Processing completed!")
    else:
        print("Failed to start processing (already running?)")


if __name__ == "__main__":
    main()