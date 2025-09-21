#!/usr/bin/env python3
"""
Basic usage example for IMAP Mail Cleanup.

This example shows the simplest way to use the email cleanup tool.
"""

from imap_cleanup import ConfigManager, EmailProcessor


def main():
    """Basic usage example."""
    print("IMAP Mail Cleanup - Basic Usage Example")
    print("=" * 45)

    # Load configuration
    config_manager = ConfigManager()

    # Show current settings
    print(f"Dry run: {config_manager.config['cleanup_settings']['dry_run']}")
    print(f"Age threshold: {config_manager.config['cleanup_settings']['age_days']} days")
    print(f"Source folders: {config_manager.config['mail_settings']['source_folders']}")
    print(f"Target folder: {config_manager.config['mail_settings']['target_folder']}")

    # Get optimal worker counts
    workers = config_manager.get_optimal_workers("auto")
    print(f"Auto-detected workers: {workers}")

    # Create processor and run
    processor = EmailProcessor(config_manager)

    print("\nStarting email cleanup...")
    total_candidates, total_moved = processor.run()

    print(f"\nResults:")
    print(f"- Candidates found: {total_candidates}")
    print(f"- Emails moved: {total_moved}")


if __name__ == "__main__":
    main()