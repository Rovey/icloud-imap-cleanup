"""
IMAP connection and operation management.

Provides thread-safe connection pooling and IMAP operations for email processing.
"""

import imaplib
import email
import socket
import threading
from email.header import decode_header, make_header
from typing import Dict, List, Set, Tuple, Optional


class IMAPConnectionPool:
    """Thread-safe IMAP connection pool."""

    def __init__(self, host: str, port: int, username: str, password: str, max_connections: int = 5):
        """Initialize IMAP connection pool.

        Args:
            host: IMAP server hostname
            port: IMAP server port
            username: IMAP username
            password: IMAP password
            max_connections: Maximum number of pooled connections
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.max_connections = max_connections
        self._pool: List[imaplib.IMAP4_SSL] = []
        self._lock = threading.Lock()

    def _create_connection(self) -> imaplib.IMAP4_SSL:
        """Create a new IMAP connection.

        Returns:
            New IMAP4_SSL connection
        """
        socket.setdefaulttimeout(30)
        conn = imaplib.IMAP4_SSL(self.host, self.port)
        conn.login(self.username, self.password)
        return conn

    def get_connection(self) -> imaplib.IMAP4_SSL:
        """Get a connection from the pool or create a new one.

        Returns:
            IMAP4_SSL connection ready for use
        """
        with self._lock:
            if self._pool:
                return self._pool.pop()
            else:
                return self._create_connection()

    def return_connection(self, conn: imaplib.IMAP4_SSL) -> None:
        """Return a connection to the pool.

        Args:
            conn: IMAP connection to return to pool
        """
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
        """Initialize IMAP manager.

        Args:
            pool: Connection pool to use for operations
            verbose: Whether to print verbose output
        """
        self.pool = pool
        self.verbose = verbose

    def ensure_folder(self, conn: imaplib.IMAP4_SSL, mailbox: str) -> None:
        """Ensure a folder exists, create if necessary.

        Args:
            conn: IMAP connection to use
            mailbox: Folder name to ensure exists
        """
        typ, data = conn.list()
        if typ != "OK":
            return
        existing = [line.decode().split(' "/" ')[-1].strip('"') for line in data if line]
        if mailbox not in existing:
            conn.create(mailbox)

    def search_uids(self, conn: imaplib.IMAP4_SSL, folder: str, query: str, max_retries: int = 2) -> Set[str]:
        """Search for UIDs matching the query.

        Args:
            conn: IMAP connection to use
            folder: Folder to search in
            query: IMAP search query
            max_retries: Maximum number of retry attempts

        Returns:
            Set of matching UIDs
        """
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
        """Perform multiple searches and return union of results.

        Args:
            conn: IMAP connection to use
            folder: Folder to search in
            queries: List of IMAP search queries

        Returns:
            Set of UIDs matching any of the queries
        """
        result = set()
        for i, query in enumerate(queries):
            if self.verbose and len(queries) > 5:
                print(f"[i] Processing search query {i + 1}/{len(queries)}")
            result |= self.search_uids(conn, folder, query)
        return result

    def fetch_headers(self, conn: imaplib.IMAP4_SSL, uid: str) -> Tuple[Optional[str], Optional[str]]:
        """Fetch email headers for a specific UID.

        Args:
            conn: IMAP connection to use
            uid: Email UID to fetch headers for

        Returns:
            Tuple of (from_header, subject) or (None, None) if failed
        """
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
        """Fetch headers for multiple UIDs using a connection from the pool.

        Args:
            folder: Folder containing the emails
            uids: List of UIDs to fetch headers for

        Returns:
            Dictionary mapping UID to (from_header, subject) tuples
        """
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
        """Move an email to the destination folder.

        Args:
            conn: IMAP connection to use (must have write access to source folder)
            uid: UID of email to move
            dest_folder: Destination folder name

        Returns:
            True if move succeeded, False otherwise
        """
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