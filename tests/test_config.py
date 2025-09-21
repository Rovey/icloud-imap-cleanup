#!/usr/bin/env python3
"""
Tests for ConfigManager functionality.
"""

import os
import tempfile
import json
from imap_cleanup.config import ConfigManager


def test_default_config():
    """Test default configuration loading."""
    # Test with non-existent files
    config_manager = ConfigManager("nonexistent.json", "nonexistent_local.json")

    # Should fall back to defaults
    assert "mail_settings" in config_manager.config
    assert "cleanup_settings" in config_manager.config
    assert config_manager.config["mail_settings"]["imap_host"] == "imap.mail.me.com"
    print("✓ Default config test passed")


def test_worker_calculation():
    """Test optimal worker calculation."""
    config_manager = ConfigManager("nonexistent.json", "nonexistent_local.json")

    # Test auto detection
    auto_workers = config_manager.get_optimal_workers("auto")
    expected_auto = max(1, min(20, (os.cpu_count() or 4) // 2))
    assert auto_workers == expected_auto

    # Test manual override
    manual_workers = config_manager.get_optimal_workers(5)
    assert manual_workers == 5

    # Test bounds
    too_low = config_manager.get_optimal_workers(0)
    assert too_low >= 1

    too_high = config_manager.get_optimal_workers(50)
    assert too_high <= 20

    print("✓ Worker calculation test passed")


def test_config_merging():
    """Test configuration file merging."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test config files
        main_config = {
            "cleanup_settings": {
                "dry_run": True,
                "age_days": 365
            }
        }

        local_config = {
            "cleanup_settings": {
                "dry_run": False  # Override dry_run
            }
        }

        main_file = os.path.join(temp_dir, "config.json")
        local_file = os.path.join(temp_dir, "local.json")

        with open(main_file, "w") as f:
            json.dump(main_config, f)

        with open(local_file, "w") as f:
            json.dump(local_config, f)

        # Test merging
        config_manager = ConfigManager(main_file, local_file)

        # Should have merged values
        assert config_manager.config["cleanup_settings"]["dry_run"] == False  # From local
        assert config_manager.config["cleanup_settings"]["age_days"] == 365   # From main

        print("✓ Config merging test passed")


def test_whitelist_loading():
    """Test whitelist loading functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test whitelist file
        whitelist_file = os.path.join(temp_dir, "whitelist.txt")
        with open(whitelist_file, "w") as f:
            f.write("test@example.com\n")
            f.write("# This is a comment\n")
            f.write("important.domain.com\n")
            f.write("\n")  # Empty line

        # Create config with whitelist settings
        config = {
            "whitelist_settings": {
                "whitelist_file": whitelist_file,
                "additional_whitelist": ["extra@test.com"]
            }
        }

        config_file = os.path.join(temp_dir, "config.json")
        with open(config_file, "w") as f:
            json.dump(config, f)

        config_manager = ConfigManager(config_file, "nonexistent.json")
        whitelist = config_manager.load_whitelist()

        # Check whitelist contents
        assert "test@example.com" in whitelist
        assert "important.domain.com" in whitelist
        assert "extra@test.com" in whitelist
        assert len([item for item in whitelist if item.startswith("#")]) == 0  # No comments

        print("✓ Whitelist loading test passed")


def main():
    """Run all tests."""
    print("Running ConfigManager tests...")
    print("=" * 40)

    test_default_config()
    test_worker_calculation()
    test_config_merging()
    test_whitelist_loading()

    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    main()