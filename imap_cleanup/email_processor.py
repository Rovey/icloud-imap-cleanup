"""
Main email processing orchestrator.

Coordinates the 3-phase email processing pipeline with threading support.
"""

import imaplib
import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import List, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

from .config import ConfigManager
from .imap_manager import IMAPConnectionPool, IMAPManager
from .email_analyzer import EmailAnalyzer


class EmailProcessor:
    """Main email processing orchestrator."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize email processor.

        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager.config
        self.config_manager = config_manager
        self.verbose = self.config["cleanup_settings"]["verbose"]

        # Initialize components
        self._setup_credentials()
        self._setup_workers()
        self._setup_components()

    def _setup_credentials(self) -> None:
        """Setup IMAP credentials from environment or config."""
        load_dotenv()
        self.username = os.getenv("IMAP_USER", "YOUR_ICLOUD_EMAIL@icloud.com")
        self.password = os.getenv("IMAP_PASS", "APP_SPECIFIC_PASSWORD")

    def _setup_workers(self) -> None:
        """Setup worker thread counts."""
        self.max_workers = self.config_manager.get_optimal_workers(
            self.config["cleanup_settings"]["max_workers"]
        )
        self.header_fetch_workers = self.config_manager.get_optimal_workers(
            self.config["cleanup_settings"]["header_fetch_workers"]
        )
        self.batch_size = self.config["cleanup_settings"]["batch_size"]

    def _setup_components(self) -> None:
        """Initialize processing components."""
        # Connection pool
        total_connections = self.max_workers + self.header_fetch_workers
        self.pool = IMAPConnectionPool(
            self.config["mail_settings"]["imap_host"],
            self.config["mail_settings"]["imap_port"],
            self.username,
            self.password,
            total_connections
        )

        # IMAP manager
        self.imap_manager = IMAPManager(self.pool, self.verbose)

        # Email analyzer
        whitelist = self.config_manager.load_whitelist()
        subject_keywords, protect_keywords = self.config_manager.get_keywords()
        self.analyzer = EmailAnalyzer(
            whitelist,
            protect_keywords,
            subject_keywords,
            self.config_manager.get_delete_domains()
        )

        # Set socket timeout
        socket.setdefaulttimeout(self.config["cleanup_settings"]["search_timeout"])

    def _get_search_date(self) -> str:
        """Get IMAP date string for age filtering.

        Returns:
            IMAP-formatted date string
        """
        age_days = self.config["cleanup_settings"]["age_days"]
        dt = datetime.now(timezone.utc) - timedelta(days=age_days)
        return dt.strftime("%d-%b-%Y")

    def _build_search_queries(self, before_date: str) -> Tuple[str, List[str], List[str]]:
        """Build IMAP search queries.

        Args:
            before_date: IMAP-formatted date string

        Returns:
            Tuple of (list_unsub_query, subject_queries, domain_queries)
        """
        # A) Messages with List-Unsubscribe header
        list_unsub_query = f'NOT FLAGGED BEFORE {before_date} HEADER List-Unsubscribe ""'

        # B) Subject keyword queries
        subject_keywords, _ = self.config_manager.get_keywords()
        max_keywords = self.config["cleanup_settings"]["max_search_keywords"]

        if len(subject_keywords) > max_keywords:
            if self.verbose:
                print(f"[i] Batching {len(subject_keywords)} keywords into groups of {max_keywords}")

            subject_batches = [subject_keywords[i:i + max_keywords]
                             for i in range(0, len(subject_keywords), max_keywords)]
            subject_queries = []
            for batch in subject_batches:
                or_terms = " OR ".join([f'SUBJECT "{kw}"' for kw in batch])
                subject_queries.append(f'NOT FLAGGED BEFORE {before_date} ({or_terms})')
        else:
            subject_queries = [f'NOT FLAGGED BEFORE {before_date} SUBJECT "{kw}"'
                             for kw in subject_keywords]

        # C) Domain deletion queries
        delete_domains = self.config_manager.get_delete_domains()
        domain_queries = [f'NOT FLAGGED BEFORE {before_date} FROM "{domain}"'
                         for domain in delete_domains]

        return list_unsub_query, subject_queries, domain_queries

    def process_folder(self, folder: str, main_conn: imaplib.IMAP4_SSL, callback=None) -> Tuple[int, int]:
        """Process a single folder and return (candidates, moved) counts.

        Args:
            folder: Folder name to process
            main_conn: Main IMAP connection for searches
            callback: Optional callback for progress updates

        Returns:
            Tuple of (total_candidates, total_moved)
        """
        if self.verbose:
            print(f"\n[i] Processing folder: {folder}")

        try:
            main_conn.select(folder, readonly=True)
        except Exception as e:
            print(f"[!] Could not select folder {folder}: {e}")
            return 0, 0

        # Build and execute searches
        before_date = self._get_search_date()
        list_unsub_query, subject_queries, domain_queries = self._build_search_queries(before_date)

        set_a = self.imap_manager.search_uids(main_conn, folder, list_unsub_query)
        set_b = self.imap_manager.union_searches(main_conn, folder, subject_queries)
        set_c = self.imap_manager.union_searches(main_conn, folder, domain_queries)

        candidates = list(set_a | set_b | set_c)

        if self.verbose:
            print(f"[i] {folder}: {len(candidates)} candidate messages")

        if not candidates:
            return 0, 0

        return self._process_candidates(folder, candidates, set_a, set_b, set_c, callback)

    def _process_candidates(self, folder: str, candidates: List[str],
                          set_a: Set[str], set_b: Set[str], set_c: Set[str], callback=None) -> Tuple[int, int]:
        """Process candidate emails through the 3-phase pipeline.

        Args:
            folder: Folder name being processed
            candidates: List of candidate email UIDs
            set_a: UIDs matching List-Unsubscribe criteria
            set_b: UIDs matching subject keyword criteria
            set_c: UIDs matching delete domain criteria
            callback: Optional callback for progress updates

        Returns:
            Tuple of (total_candidates, total_moved)
        """
        total_candidates = 0
        total_moved = 0

        # Phase 1: Fetch headers in parallel
        if self.verbose:
            print(f"[i] Step 1: Fetching headers for {len(candidates)} emails using {self.header_fetch_workers} threads")

        if callback:
            callback.on_phase_start("Fetching email headers", len(candidates))

        header_batches = [candidates[i:i + self.batch_size]
                         for i in range(0, len(candidates), self.batch_size)]
        all_headers = {}
        headers_processed = 0

        with ThreadPoolExecutor(max_workers=self.header_fetch_workers) as executor:
            header_futures = []
            for batch in header_batches:
                future = executor.submit(self.imap_manager.fetch_headers_batch, folder, batch)
                header_futures.append(future)

            for future in as_completed(header_futures):
                try:
                    batch_headers = future.result()
                    all_headers.update(batch_headers)
                    headers_processed += len(batch_headers)

                    if callback:
                        callback.on_progress(headers_processed, len(candidates), f"Fetched headers")
                except Exception as e:
                    if self.verbose:
                        print(f"[!] Header fetch error: {e}")

        # Phase 2: Process decisions in parallel
        if self.verbose:
            print(f"[i] Step 2: Processing decisions for {len(all_headers)} emails")

        if callback:
            callback.on_phase_start("Analyzing emails", len(all_headers))

        actions_to_execute = []
        decisions_processed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            decision_futures = {}
            for uid, (from_raw, subject) in all_headers.items():
                future = executor.submit(
                    self.analyzer.should_process_email,
                    uid, from_raw, subject, set_a, set_b, set_c
                )
                decision_futures[future] = uid

            for future in as_completed(decision_futures):
                uid = decision_futures[future]
                try:
                    decision = future.result()
                    decisions_processed += 1

                    if decision:
                        action, reason, addr, subject = decision
                        if action == "process":
                            actions_to_execute.append((uid, reason, addr, subject))
                            total_candidates += 1
                            if callback:
                                callback.on_email_processed("candidate", uid, addr, subject, reason)
                        elif action == "skip":
                            if callback:
                                callback.on_email_processed("skip", uid, addr, subject, reason)
                            if self.verbose:
                                print(f"  - SKIP ({reason}): {addr} | {subject}")

                    if callback:
                        callback.on_progress(decisions_processed, len(all_headers), f"Analyzed emails")

                except Exception as e:
                    if self.verbose:
                        print(f"[!] Decision processing error for UID {uid}: {e}")

        # Phase 3: Execute actions in parallel
        if actions_to_execute:
            if self.verbose:
                print(f"[i] Step 3: Executing actions for {len(actions_to_execute)} emails using {self.max_workers} threads")

            if callback:
                callback.on_phase_start("Moving emails", len(actions_to_execute))

            total_moved = self._execute_actions(folder, actions_to_execute, callback)

        return total_candidates, total_moved

    def _execute_actions(self, folder: str, actions: List[Tuple[str, str, str, str]], callback=None) -> int:
        """Execute email actions in parallel.

        Args:
            folder: Source folder name
            actions: List of (uid, reason, addr, subject) tuples to process
            callback: Optional callback for progress updates

        Returns:
            Number of emails successfully moved
        """
        target_folder = self.config["mail_settings"]["target_folder"]
        dry_run = self.config["cleanup_settings"]["dry_run"]
        total_moved = 0

        action_batches = [actions[i:i + self.batch_size]
                         for i in range(0, len(actions), self.batch_size)]

        # Shared progress tracking using mutable object
        progress_lock = threading.Lock()
        progress_data = {"processed": 0}
        stop_progress_thread = threading.Event()

        def progress_monitor():
            """Monitor and report progress every 0.5 seconds."""
            last_reported = 0
            while not stop_progress_thread.wait(0.5):
                with progress_lock:
                    current = progress_data["processed"]
                if current != last_reported and callback:
                    callback.on_progress(current, len(actions), f"Moved emails")
                    last_reported = current
                if current >= len(actions):
                    break

        # Start progress monitoring thread if we have a callback
        progress_thread = None
        if callback:
            progress_thread = threading.Thread(target=progress_monitor, daemon=True)
            progress_thread.start()

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                action_futures = []
                for batch in action_batches:
                    future = executor.submit(
                        self._execute_action_batch,
                        folder, batch, target_folder, dry_run,
                        progress_lock, progress_data
                    )
                    action_futures.append(future)

                for future in as_completed(action_futures):
                    try:
                        moved_count = future.result()
                        total_moved += moved_count
                    except Exception as e:
                        if self.verbose:
                            print(f"[!] Action execution error: {e}")

        finally:
            # Stop progress monitoring
            stop_progress_thread.set()
            if progress_thread:
                progress_thread.join(timeout=1.0)

            # Final progress update
            if callback:
                with progress_lock:
                    final_count = progress_data["processed"]
                callback.on_progress(final_count, len(actions), f"Moved emails")

        return total_moved

    def _execute_action_batch(self, folder: str, actions: List[Tuple[str, str, str, str]],
                             target_folder: str, dry_run: bool, progress_lock=None, progress_data=None) -> int:
        """Execute a batch of actions.

        Args:
            folder: Source folder name
            actions: List of (uid, reason, addr, subject) tuples
            target_folder: Destination folder name
            dry_run: Whether to perform dry run only
            progress_lock: Optional lock for progress updates
            progress_data: Optional shared progress data dictionary

        Returns:
            Number of emails successfully moved
        """
        moved_count = 0
        conn = self.pool.get_connection()

        try:
            if not dry_run:
                conn.select(folder)  # Need write access for moves

            for uid, match_reason, addr, subject in actions:
                if dry_run:
                    if self.verbose:
                        print(f"  - DRY-RUN would move UID {uid} from {folder} → {target_folder} | {addr} | {match_reason} | {subject}")
                    moved_count += 1  # Count dry run actions as processed
                else:
                    try:
                        if self.imap_manager.move_email(conn, uid, target_folder):
                            moved_count += 1
                            if self.verbose:
                                print(f"  - Moved UID {uid} to {target_folder} | {match_reason}")
                        else:
                            if self.verbose:
                                print(f"  - FAILED to move UID {uid}")
                    except Exception as e:
                        if self.verbose:
                            print(f"  - Error moving UID {uid}: {e}")

                # Update shared progress after each email
                if progress_lock and progress_data:
                    with progress_lock:
                        progress_data["processed"] += 1

        finally:
            self.pool.return_connection(conn)

        return moved_count

    def run(self, callback=None) -> Tuple[int, int]:
        """Run the complete email cleanup process.

        Args:
            callback: Optional callback object for progress updates

        Returns:
            Tuple of (total_candidates, total_moved)
        """
        if self.verbose:
            cores = os.cpu_count() or 4
            print(f"[i] System cores: {cores}, Using {self.max_workers} processing workers + {self.header_fetch_workers} header fetch workers")

        # Notify callback of start
        if callback:
            stats = self.get_stats()
            callback.on_start(stats)

        # Create main connection
        main_conn = self.pool.get_connection()

        try:
            if self.verbose:
                print("[i] Logged in to iCloud IMAP")

            # Ensure target folder exists
            target_folder = self.config["mail_settings"]["target_folder"]
            self.imap_manager.ensure_folder(main_conn, target_folder)

            before_date = self._get_search_date()
            age_days = self.config["cleanup_settings"]["age_days"]
            if self.verbose:
                print(f"[i] Only touching messages BEFORE {before_date} (>{age_days} days old)")

            # Process all folders
            total_candidates = 0
            total_moved = 0
            source_folders = self.config["mail_settings"]["source_folders"]

            for folder_index, folder in enumerate(source_folders, 1):
                if callback:
                    callback.on_folder_start(folder, len(source_folders), folder_index)

                candidates, moved = self.process_folder(folder, main_conn, callback)
                total_candidates += candidates
                total_moved += moved

                if callback:
                    callback.on_folder_complete(folder, candidates, moved)

            if callback:
                callback.on_complete(total_candidates, total_moved)

            return total_candidates, total_moved

        finally:
            self.pool.return_connection(main_conn)
            self.pool.close_all()

    def get_stats(self) -> dict:
        """Get processing statistics and configuration.

        Returns:
            Dictionary containing current configuration and capabilities
        """
        return {
            "max_workers": self.max_workers,
            "header_fetch_workers": self.header_fetch_workers,
            "batch_size": self.batch_size,
            "cpu_cores": os.cpu_count(),
            "total_connections": self.max_workers + self.header_fetch_workers,
            "dry_run": self.config["cleanup_settings"]["dry_run"],
            "age_days": self.config["cleanup_settings"]["age_days"],
            "source_folders": self.config["mail_settings"]["source_folders"],
            "target_folder": self.config["mail_settings"]["target_folder"],
        }