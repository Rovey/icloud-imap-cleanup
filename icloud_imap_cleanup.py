#!/usr/bin/env python3
"""
iCloud IMAP cleaner (safe mode): moves noisy/low-value mail to a review folder.

This refactored version uses a clean class-based architecture following Python standards.

Requirements: Python 3.9+, standard library only.
Usage:
  1) Create an app-specific password at https://appleid.apple.com/
  2) Edit USERNAME and PASSWORD below (or set env vars IMAP_USER/IMAP_PASS)
  3) Adjust settings/whitelist as needed
  4) Run: python icloud_imap_cleanup.py
"""

import imaplib
import email
import os
import json
import socket
import threading
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from typing import Dict, List, Set, Tuple, Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv


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
        """Recursively merge configuration dictionaries."""
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
        """Calculate optimal number of workers based on CPU cores."""
        if isinstance(config_value, int) and config_value > 0:
            return min(max(config_value, min_workers), max_workers)

        cpu_count = os.cpu_count() or 4
        optimal = max(int(cpu_count * default_ratio), min_workers)
        return min(optimal, max_workers)

    def load_whitelist(self) -> Set[str]:
        """Load whitelist from file and additional entries."""
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


class IMAPConnectionPool:
    """Thread-safe IMAP connection pool."""

    def __init__(self, host: str, port: int, username: str, password: str, max_connections: int = 5):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.max_connections = max_connections
        self._pool: List[imaplib.IMAP4_SSL] = []
        self._lock = threading.Lock()

    def _create_connection(self) -> imaplib.IMAP4_SSL:
        """Create a new IMAP connection."""
        socket.setdefaulttimeout(30)
        conn = imaplib.IMAP4_SSL(self.host, self.port)
        conn.login(self.username, self.password)
        return conn

    def get_connection(self) -> imaplib.IMAP4_SSL:
        """Get a connection from the pool or create a new one."""
        with self._lock:
            if self._pool:
                return self._pool.pop()
            else:
                return self._create_connection()

    def return_connection(self, conn: imaplib.IMAP4_SSL) -> None:
        """Return a connection to the pool."""
        with self._lock:
            if len(self._pool) < self.max_connections:
                self._pool.append(conn)
            else:
                try:
                    conn.logout()
                except:
                    pass

    def close_all(self) -> None:
        """Close all pooled connections."""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.logout()
                except:
                    pass
            self._pool.clear()


class IMAPManager:
    """Manages IMAP operations and queries."""

    def __init__(self, pool: IMAPConnectionPool, verbose: bool = True):
        self.pool = pool
        self.verbose = verbose

    def ensure_folder(self, conn: imaplib.IMAP4_SSL, mailbox: str) -> None:
        """Ensure a folder exists, create if necessary."""
        typ, data = conn.list()
        if typ != "OK":
            return
        existing = [line.decode().split(' "/" ')[-1].strip('"') for line in data if line]
        if mailbox not in existing:
            conn.create(mailbox)

    def search_uids(self, conn: imaplib.IMAP4_SSL, folder: str, query: str, max_retries: int = 2) -> Set[str]:
        """Search for UIDs matching the query."""
        conn.select(folder, readonly=True)

        for attempt in range(max_retries + 1):
            try:
                if self.verbose and attempt > 0:
                    print(f"[i] Retrying search (attempt {attempt + 1})")

                typ, data = conn.uid("SEARCH", None, query)
                if typ != "OK" or not data or data[0] is None:
                    return set()

                return set(data[0].decode().split())

            except (socket.timeout, socket.error) as e:
                if self.verbose:
                    print(f"[!] Network timeout/error on search attempt {attempt + 1}: {e}")
                if attempt < max_retries:
                    continue
                else:
                    print(f"[!] Search failed after {max_retries + 1} attempts, skipping")
                    return set()
            except Exception as e:
                if self.verbose:
                    print(f"[!] Search error: {e}")
                return set()

        return set()

    def union_searches(self, conn: imaplib.IMAP4_SSL, folder: str, queries: List[str]) -> Set[str]:
        """Perform multiple searches and return union of results."""
        result = set()
        for i, query in enumerate(queries):
            if self.verbose and len(queries) > 5:
                print(f"[i] Processing search query {i + 1}/{len(queries)}")
            result |= self.search_uids(conn, folder, query)
        return result

    def fetch_headers(self, conn: imaplib.IMAP4_SSL, uid: str) -> Tuple[Optional[str], Optional[str]]:
        """Fetch email headers for a specific UID."""
        try:
            typ, msg_data = conn.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            if typ != "OK" or not msg_data or msg_data[0] is None:
                return None, None

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            subject = str(make_header(decode_header(msg.get("Subject", "")))).strip()
            from_raw = msg.get("From", "")
            return from_raw, subject
        except Exception as e:
            if self.verbose:
                print(f"[!] Error fetching headers for UID {uid}: {e}")
            return None, None

    def fetch_headers_batch(self, folder: str, uids: List[str]) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """Fetch headers for multiple UIDs using a connection from the pool."""
        conn = self.pool.get_connection()
        results = {}

        try:
            conn.select(folder, readonly=True)
            for uid in uids:
                results[uid] = self.fetch_headers(conn, uid)
        finally:
            self.pool.return_connection(conn)

        return results

    def move_email(self, conn: imaplib.IMAP4_SSL, uid: str, dest_folder: str) -> bool:
        """Move an email to the destination folder."""
        try:
            # Try UID MOVE (RFC 6851). If unsupported, fallback to COPY+DELETE.
            typ, _ = conn.uid("MOVE", uid, dest_folder)
            if typ == "OK":
                return True

            # Fallback
            typ, _ = conn.uid("COPY", uid, dest_folder)
            if typ != "OK":
                return False

            conn.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
            conn.expunge()
            return True
        except Exception:
            return False


class EmailAnalyzer:
    """Analyzes emails and makes processing decisions."""

    def __init__(self, whitelist: Set[str], protect_keywords: List[str],
                 subject_keywords: List[str], delete_domains: List[str]):
        self.whitelist = whitelist
        self.protect_keywords = protect_keywords
        self.subject_keywords = subject_keywords
        self.delete_domains = delete_domains

    def parse_from_address(self, from_header: str) -> Tuple[str, str]:
        """Extract email address and domain from From header."""
        addr = email.utils.parseaddr(from_header)[1].lower()
        domain = addr.split("@")[-1] if "@" in addr else ""
        return addr, domain

    def should_process_email(self, uid: str, from_raw: Optional[str], subject: Optional[str],
                           set_a: Set[str], set_b: Set[str], set_c: Set[str]) -> Optional[Tuple[str, str, str, str]]:
        """Determine if an email should be processed and why."""
        if from_raw is None:
            return None

        addr, domain = self.parse_from_address(from_raw)

        # Whitelist check
        if addr in self.whitelist or domain in self.whitelist:
            return ("skip", "whitelist", addr, subject or "")

        # Protect keywords (never move)
        subj_lower = (subject or "").lower()
        if any(pk in subj_lower for pk in self.protect_keywords):
            return ("skip", "protected subject", addr, subject or "")

        # Determine match reason
        match_reason = "unknown"
        if uid in set_a:
            match_reason = "List-Unsubscribe header"
        elif uid in set_b:
            # Find which keyword matched
            for kw in self.subject_keywords:
                if kw.lower() in subj_lower:
                    match_reason = f"subject keyword '{kw}'"
                    break
            if match_reason == "unknown":
                match_reason = "subject keyword"
        elif uid in set_c:
            # Find which domain matched
            for del_domain in self.delete_domains:
                if domain == del_domain or addr.endswith(f"@{del_domain}"):
                    match_reason = f"delete domain '{del_domain}'"
                    break
            if match_reason == "unknown":
                match_reason = "delete domain"

        return ("process", match_reason, addr, subject or "")


class EmailProcessor:
    """Main email processing orchestrator."""

    def __init__(self, config_manager: ConfigManager):
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
        self.analyzer = EmailAnalyzer(
            whitelist,
            self.config["protect_keywords"],
            self.config["subject_keywords"],
            self.config["delete_domains"]
        )

        # Set socket timeout
        socket.setdefaulttimeout(self.config["cleanup_settings"]["search_timeout"])

    def _get_search_date(self) -> str:
        """Get IMAP date string for age filtering."""
        age_days = self.config["cleanup_settings"]["age_days"]
        dt = datetime.now(timezone.utc) - timedelta(days=age_days)
        return dt.strftime("%d-%b-%Y")

    def _build_search_queries(self, before_date: str) -> Tuple[str, List[str], List[str]]:
        """Build IMAP search queries."""
        # A) Messages with List-Unsubscribe header
        list_unsub_query = f'NOT FLAGGED BEFORE {before_date} HEADER List-Unsubscribe ""'

        # B) Subject keyword queries
        subject_keywords = self.config["subject_keywords"]
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
        domain_queries = [f'NOT FLAGGED BEFORE {before_date} FROM "{domain}"'
                         for domain in self.config["delete_domains"]]

        return list_unsub_query, subject_queries, domain_queries

    def process_folder(self, folder: str, main_conn: imaplib.IMAP4_SSL) -> Tuple[int, int]:
        """Process a single folder and return (candidates, moved) counts."""
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

        return self._process_candidates(folder, candidates, set_a, set_b, set_c)

    def _process_candidates(self, folder: str, candidates: List[str],
                          set_a: Set[str], set_b: Set[str], set_c: Set[str]) -> Tuple[int, int]:
        """Process candidate emails through the 3-phase pipeline."""
        total_candidates = 0
        total_moved = 0

        # Phase 1: Fetch headers in parallel
        if self.verbose:
            print(f"[i] Step 1: Fetching headers for {len(candidates)} emails using {self.header_fetch_workers} threads")

        header_batches = [candidates[i:i + self.batch_size]
                         for i in range(0, len(candidates), self.batch_size)]
        all_headers = {}

        with ThreadPoolExecutor(max_workers=self.header_fetch_workers) as executor:
            header_futures = []
            for batch in header_batches:
                future = executor.submit(self.imap_manager.fetch_headers_batch, folder, batch)
                header_futures.append(future)

            for future in as_completed(header_futures):
                try:
                    batch_headers = future.result()
                    all_headers.update(batch_headers)
                except Exception as e:
                    if self.verbose:
                        print(f"[!] Header fetch error: {e}")

        # Phase 2: Process decisions in parallel
        if self.verbose:
            print(f"[i] Step 2: Processing decisions for {len(all_headers)} emails")

        actions_to_execute = []

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
                    if decision:
                        action, reason, addr, subject = decision
                        if action == "process":
                            actions_to_execute.append((uid, reason, addr, subject))
                            total_candidates += 1
                        elif action == "skip" and self.verbose:
                            print(f"  - SKIP ({reason}): {addr} | {subject}")
                except Exception as e:
                    if self.verbose:
                        print(f"[!] Decision processing error for UID {uid}: {e}")

        # Phase 3: Execute actions in parallel
        if actions_to_execute:
            if self.verbose:
                print(f"[i] Step 3: Executing actions for {len(actions_to_execute)} emails using {self.max_workers} threads")

            total_moved = self._execute_actions(folder, actions_to_execute)

        return total_candidates, total_moved

    def _execute_actions(self, folder: str, actions: List[Tuple[str, str, str, str]]) -> int:
        """Execute email actions in parallel."""
        target_folder = self.config["mail_settings"]["target_folder"]
        dry_run = self.config["cleanup_settings"]["dry_run"]
        total_moved = 0

        action_batches = [actions[i:i + self.batch_size]
                         for i in range(0, len(actions), self.batch_size)]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            action_futures = []
            for batch in action_batches:
                future = executor.submit(self._execute_action_batch, folder, batch, target_folder, dry_run)
                action_futures.append(future)

            for future in as_completed(action_futures):
                try:
                    moved_count = future.result()
                    total_moved += moved_count
                except Exception as e:
                    if self.verbose:
                        print(f"[!] Action execution error: {e}")

        return total_moved

    def _execute_action_batch(self, folder: str, actions: List[Tuple[str, str, str, str]],
                             target_folder: str, dry_run: bool) -> int:
        """Execute a batch of actions."""
        moved_count = 0
        conn = self.pool.get_connection()

        try:
            if not dry_run:
                conn.select(folder)  # Need write access for moves

            for uid, match_reason, addr, subject in actions:
                if dry_run:
                    if self.verbose:
                        print(f"  - DRY-RUN would move UID {uid} from {folder} → {target_folder} | {addr} | {match_reason} | {subject}")
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

        finally:
            self.pool.return_connection(conn)

        return moved_count

    def run(self) -> None:
        """Run the complete email cleanup process."""
        if self.verbose:
            cores = os.cpu_count() or 4
            print(f"[i] System cores: {cores}, Using {self.max_workers} processing workers + {self.header_fetch_workers} header fetch workers")

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

            for folder in self.config["mail_settings"]["source_folders"]:
                candidates, moved = self.process_folder(folder, main_conn)
                total_candidates += candidates
                total_moved += moved

            # Summary
            print(f"\n[done] Candidates considered: {total_candidates}")
            if not self.config["cleanup_settings"]["dry_run"]:
                print(f"[done] Actually moved:      {total_moved}")
            else:
                print("[note] DRY-RUN enabled — no changes were made. Set dry_run=false in config.json to execute.")

        finally:
            self.pool.return_connection(main_conn)
            self.pool.close_all()


def main():
    """Main entry point."""
    try:
        config_manager = ConfigManager()
        processor = EmailProcessor(config_manager)
        processor.run()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()