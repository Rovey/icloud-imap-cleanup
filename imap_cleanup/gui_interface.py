"""
GUI Interface base class for IMAP Mail Cleanup.

Provides a clean interface that GUI implementations can use.
This separates the processing logic from UI concerns.
"""

import threading
from typing import Callable, Optional, Dict, Any
from .config import ConfigManager
from .email_processor import EmailProcessor


class ProcessingCallback:
    """Callback interface for GUI progress updates."""

    def on_start(self, stats: Dict[str, Any]) -> None:
        """Called when processing starts."""
        pass

    def on_folder_start(self, folder: str, total_folders: int, current_folder: int) -> None:
        """Called when starting to process a folder."""
        pass

    def on_phase_start(self, phase: str, total_items: int) -> None:
        """Called when starting a processing phase."""
        pass

    def on_progress(self, current: int, total: int, message: str = "") -> None:
        """Called to report progress within a phase."""
        pass

    def on_email_processed(self, action: str, uid: str, from_addr: str, subject: str, reason: str) -> None:
        """Called when an email is processed."""
        pass

    def on_folder_complete(self, folder: str, candidates: int, moved: int) -> None:
        """Called when folder processing is complete."""
        pass

    def on_complete(self, total_candidates: int, total_moved: int) -> None:
        """Called when all processing is complete."""
        pass

    def on_error(self, error: str, details: str = "") -> None:
        """Called when an error occurs."""
        pass


class GUIInterface:
    """GUI interface for email processing operations."""

    def __init__(self, config_file: str = "config.json", local_config_file: str = "config.local.json"):
        """Initialize GUI interface.

        Args:
            config_file: Main configuration file path
            local_config_file: Local overrides configuration file path
        """
        self.config_manager = ConfigManager(config_file, local_config_file)
        self.processor: Optional[EmailProcessor] = None
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_requested = False

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration.

        Returns:
            Complete configuration dictionary
        """
        return self.config_manager.config

    def update_config(self, config_updates: Dict[str, Any]) -> None:
        """Update configuration values.

        Args:
            config_updates: Dictionary of configuration updates to apply
        """
        for section, values in config_updates.items():
            if section in self.config_manager.config:
                if isinstance(values, dict):
                    self.config_manager.config[section].update(values)
                else:
                    self.config_manager.config[section] = values

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics and capabilities.

        Returns:
            Dictionary containing processing configuration and stats
        """
        if not self.processor:
            self.processor = EmailProcessor(self.config_manager)

        return self.processor.get_stats()

    def validate_credentials(self) -> bool:
        """Validate IMAP credentials.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            processor = EmailProcessor(self.config_manager)
            # Try to create a connection to test credentials
            conn = processor.pool.get_connection()
            processor.pool.return_connection(conn)
            return True
        except Exception:
            return False

    def test_connection(self) -> tuple[bool, str]:
        """Test IMAP connection.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            processor = EmailProcessor(self.config_manager)
            conn = processor.pool.get_connection()
            processor.pool.return_connection(conn)
            processor.pool.close_all()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)

    def start_processing(self, callback: ProcessingCallback) -> bool:
        """Start email processing in a background thread.

        Args:
            callback: Callback object for progress updates

        Returns:
            True if processing started, False if already running
        """
        if self._processing_thread and self._processing_thread.is_alive():
            return False

        self._stop_requested = False
        self._processing_thread = threading.Thread(
            target=self._run_processing,
            args=(callback,),
            daemon=True
        )
        self._processing_thread.start()
        return True

    def stop_processing(self) -> None:
        """Request processing to stop."""
        self._stop_requested = True

    def is_processing(self) -> bool:
        """Check if processing is currently running.

        Returns:
            True if processing, False otherwise
        """
        return self._processing_thread and self._processing_thread.is_alive()

    def _run_processing(self, callback: ProcessingCallback) -> None:
        """Run the processing with callbacks (internal method)."""
        try:
            self.processor = EmailProcessor(self.config_manager)
            stats = self.processor.get_stats()
            callback.on_start(stats)

            total_candidates, total_moved = self.processor.run()

            callback.on_complete(total_candidates, total_moved)

        except Exception as e:
            callback.on_error(str(e))

    def get_whitelist(self) -> set[str]:
        """Get current whitelist entries.

        Returns:
            Set of whitelisted email addresses and domains
        """
        return self.config_manager.load_whitelist()

    def add_to_whitelist(self, entry: str) -> None:
        """Add an entry to the whitelist.

        Args:
            entry: Email address or domain to whitelist
        """
        current_additional = self.config_manager.config["whitelist_settings"]["additional_whitelist"]
        if entry not in current_additional:
            current_additional.append(entry)

    def remove_from_whitelist(self, entry: str) -> None:
        """Remove an entry from the additional whitelist.

        Args:
            entry: Email address or domain to remove
        """
        current_additional = self.config_manager.config["whitelist_settings"]["additional_whitelist"]
        if entry in current_additional:
            current_additional.remove(entry)

    def preview_processing(self, max_emails: int = 10) -> list[dict]:
        """Preview what emails would be processed without actually processing them.

        Args:
            max_emails: Maximum number of emails to preview

        Returns:
            List of email dictionaries with preview information
        """
        # This would be implemented to show a preview of what would be processed
        # For now, return empty list as placeholder
        return []