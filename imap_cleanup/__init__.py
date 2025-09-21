"""
IMAP Mail Cleanup Package

A threaded email cleanup tool for iCloud IMAP with GUI support.
"""

__version__ = "2.0.0"
__author__ = "Generated with Claude Code"

from .config import ConfigManager
from .email_analyzer import EmailAnalyzer
from .email_processor import EmailProcessor
from .imap_manager import IMAPManager, IMAPConnectionPool

__all__ = [
    "ConfigManager",
    "EmailAnalyzer",
    "EmailProcessor",
    "IMAPManager",
    "IMAPConnectionPool",
]