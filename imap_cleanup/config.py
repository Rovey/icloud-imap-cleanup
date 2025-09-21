"""
Configuration management for IMAP Mail Cleanup.

Handles loading and validation of configuration files with support for
local overrides and automatic CPU core detection.
"""

import json
import os
from typing import Dict, List, Set, Union, Any


class ConfigManager:
    """Handles configuration loading and validation."""

    DEFAULT_CONFIG = {
        "mail_settings": {
            "imap_host": "imap.mail.me.com",
            "imap_port": 993,
            "source_folders": ["INBOX", "Archive"],
            "target_folder": "Review/Delete"
        },
        "cleanup_settings": {
            "age_days": 365,
            "dry_run": True,
            "verbose": True,
            "search_timeout": 30,
            "max_search_keywords": 10,
            "max_workers": "auto",
            "batch_size": 50,
            "header_fetch_workers": "auto"
        },
        "subject_keywords": [
            "unsubscribe", "newsletter", "nieuwsbrief", "promo", "promotion", "actie",
            "deal", "korting", "sale", "update", "digest", "marketing", "leveringsupdate",
            "tracking", "pakket", "afgeleverd", "bezorgd", "shipping", "delivered",
            "transactiebevestiging", "bevestiging", "reactie", "kopie", "bestelling",
            "order", "verzending", "bezorging", "behandeling", "bedankt", "thank",
            "confirmation", "confirmed", "shipment", "delivery", "processing",
            "Wat vond u"
        ],
        "protect_keywords": [
            "factuur", "rekening", "nota", "bill", "invoice",
            "belasting", "btw", "tax", "vat", "aanslag",
            "incasso", "aanmaning", "reminder", "overdue",
            "refund", "terugbetaling", "chargeback",
            "saldo", "afschrift", "account statement"
        ],
        "whitelist_settings": {
            "whitelist_file": "whitelist.txt",
            "additional_whitelist": []
        },
        "delete_domains": []
    }

    def __init__(self, config_file: str = "config.json", local_config_file: str = "config.local.json"):
        """Initialize configuration manager.

        Args:
            config_file: Main configuration file path
            local_config_file: Local overrides configuration file path
        """
        self.config_file = config_file
        self.local_config_file = local_config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from files with fallback to defaults."""
        config = self.DEFAULT_CONFIG.copy()

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            self._merge_config(config, user_config)
        except FileNotFoundError:
            print(f"[!] {self.config_file} not found, using default configuration")
        except json.JSONDecodeError as e:
            print(f"[!] Error parsing {self.config_file}: {e}, using default configuration")

        # Load local overrides
        try:
            with open(self.local_config_file, "r", encoding="utf-8") as f:
                local_config = json.load(f)
            self._merge_config(config, local_config)
            print(f"[i] Loaded local configuration overrides from {self.local_config_file}")
        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            print(f"[!] Error parsing {self.local_config_file}: {e}, ignoring local config")

        return config

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge configuration dictionaries.

        Args:
            base: Base configuration dictionary to merge into
            override: Override configuration dictionary to merge from
        """
        for section, values in override.items():
            if section not in base:
                base[section] = values
            elif isinstance(values, dict) and isinstance(base[section], dict):
                self._merge_config(base[section], values)
            else:
                base[section] = values

    def get_optimal_workers(self, config_value: Union[str, int],
                           default_ratio: float = 0.5,
                           min_workers: int = 1,
                           max_workers: int = 20) -> int:
        """Calculate optimal number of workers based on CPU cores.

        Args:
            config_value: Either "auto" or specific number of workers
            default_ratio: Ratio of CPU cores to use when "auto"
            min_workers: Minimum number of workers
            max_workers: Maximum number of workers

        Returns:
            Optimal number of worker threads
        """
        if isinstance(config_value, int) and config_value > 0:
            return min(max(config_value, min_workers), max_workers)

        cpu_count = os.cpu_count() or 4
        optimal = max(int(cpu_count * default_ratio), min_workers)
        return min(optimal, max_workers)

    def load_whitelist(self) -> Set[str]:
        """Load whitelist from file and additional entries.

        Returns:
            Set of whitelisted email addresses and domains
        """
        whitelist_file = self.config["whitelist_settings"]["whitelist_file"]
        additional_whitelist = set(self.config["whitelist_settings"]["additional_whitelist"])

        items = set(w.strip().lower() for w in additional_whitelist if w.strip())

        try:
            with open(whitelist_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        items.add(line.lower())
        except FileNotFoundError:
            pass

        return items

    def get_mail_settings(self) -> Dict[str, Any]:
        """Get mail server settings."""
        return self.config["mail_settings"]

    def get_cleanup_settings(self) -> Dict[str, Any]:
        """Get cleanup processing settings."""
        return self.config["cleanup_settings"]

    def get_keywords(self) -> tuple[List[str], List[str]]:
        """Get subject and protect keywords.

        Returns:
            Tuple of (subject_keywords, protect_keywords)
        """
        return self.config["subject_keywords"], self.config["protect_keywords"]

    def get_delete_domains(self) -> List[str]:
        """Get domains to delete emails from."""
        return self.config["delete_domains"]