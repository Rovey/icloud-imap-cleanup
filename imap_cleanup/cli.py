"""
Command Line Interface for IMAP Mail Cleanup.

Provides the CLI entry point for the email cleanup tool.
"""

import sys
from .config import ConfigManager
from .email_processor import EmailProcessor


def main():
    """CLI entry point for IMAP Mail Cleanup."""
    try:
        print("IMAP Mail Cleanup v2.0.0")
        print("=" * 40)

        # Initialize configuration and processor
        config_manager = ConfigManager()
        processor = EmailProcessor(config_manager)

        # Run the cleanup process
        total_candidates, total_moved = processor.run()

        # Final summary
        print(f"\n[done] Candidates considered: {total_candidates}")
        if not config_manager.config["cleanup_settings"]["dry_run"]:
            print(f"[done] Actually moved:      {total_moved}")
        else:
            print("[note] DRY-RUN enabled — no changes were made. Set dry_run=false in config.json to execute.")

        return 0

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        return 1
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main())