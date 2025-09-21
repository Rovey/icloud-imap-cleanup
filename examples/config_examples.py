#!/usr/bin/env python3
"""
Configuration examples for IMAP Mail Cleanup.

Shows how to programmatically modify configuration.
"""

from imap_cleanup import ConfigManager


def main():
    """Configuration examples."""
    print("IMAP Mail Cleanup - Configuration Examples")
    print("=" * 50)

    # Load configuration
    config_manager = ConfigManager()

    # Example 1: Override worker counts
    print("Example 1: Manual worker configuration")
    manual_workers = config_manager.get_optimal_workers(4)  # Force 4 workers
    auto_workers = config_manager.get_optimal_workers("auto")  # Auto-detect
    print(f"Manual workers: {manual_workers}")
    print(f"Auto workers: {auto_workers}")

    # Example 2: Modify configuration programmatically
    print("\nExample 2: Programmatic configuration")
    original_dry_run = config_manager.config["cleanup_settings"]["dry_run"]
    print(f"Original dry run: {original_dry_run}")

    # Temporarily change settings
    config_manager.config["cleanup_settings"]["dry_run"] = True
    config_manager.config["cleanup_settings"]["age_days"] = 180

    print(f"Modified dry run: {config_manager.config['cleanup_settings']['dry_run']}")
    print(f"Modified age days: {config_manager.config['cleanup_settings']['age_days']}")

    # Example 3: Whitelist management
    print("\nExample 3: Whitelist operations")
    whitelist = config_manager.load_whitelist()
    print(f"Current whitelist size: {len(whitelist)}")

    # Add entries to additional whitelist
    additional = config_manager.config["whitelist_settings"]["additional_whitelist"]
    if "important@company.com" not in additional:
        additional.append("important@company.com")
        print("Added important@company.com to whitelist")

    # Example 4: Keywords management
    print("\nExample 4: Keywords configuration")
    subject_keywords, protect_keywords = config_manager.get_keywords()
    print(f"Subject keywords: {len(subject_keywords)}")
    print(f"Protect keywords: {len(protect_keywords)}")
    print(f"First 5 subject keywords: {subject_keywords[:5]}")

    # Example 5: Mail settings
    print("\nExample 5: Mail server settings")
    mail_settings = config_manager.get_mail_settings()
    print(f"IMAP host: {mail_settings['imap_host']}")
    print(f"IMAP port: {mail_settings['imap_port']}")
    print(f"Source folders: {mail_settings['source_folders']}")


if __name__ == "__main__":
    main()