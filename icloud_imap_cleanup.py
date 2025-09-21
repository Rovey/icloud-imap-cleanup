#!/usr/bin/env python3
"""
iCloud IMAP cleaner (safe mode): moves noisy/low-value mail to a review folder.
- Matches newsletters/marketing using List-Unsubscribe header OR subject keywords
- Only messages older than AGE_DAYS
- Skips flagged/starred messages
- Respects a whitelist (emails and/or domains)
- Works across multiple source folders (e.g., INBOX and Archive)
- Default is DRY-RUN (no changes). Set DRY_RUN = False to execute.

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
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ======== CONFIG =========
IMAP_HOST = "imap.mail.me.com"
IMAP_PORT = 993
USERNAME = os.getenv("IMAP_USER", "YOUR_ICLOUD_EMAIL@icloud.com")
PASSWORD = os.getenv("IMAP_PASS", "APP_SPECIFIC_PASSWORD")

SOURCE_FOLDERS = ["INBOX", "Archive"]  # Folders to scan
TARGET_FOLDER  = "Review/Delete"       # Destination folder (will be created if absent)

AGE_DAYS = 365  # Only touch messages older than 1 year
SUBJECT_KEYWORDS = [
    "unsubscribe", "newsletter", "nieuwsbrief", "promo", "promotion", "actie",
    "deal", "korting", "sale", "update", "digest", "marketing", "leveringsupdate",
    "tracking", "pakket", "afgeleverd", "bezorgd", "shipping", "delivered",
    "transactiebevestiging", "bevestiging", "reactie", "kopie", "bestelling",
    "order", "verzending", "bezorging", "behandeling", "bedankt", "thank",
    "confirmation", "confirmed", "shipment", "delivery", "processing",
    "Wat vond u"
]

# Extra safety: subjects that should NEVER be auto-moved (leave empty if you don't want this)
# Note: Only protects truly important financial docs - old order confirmations are usually safe to archive
PROTECT_KEYWORDS = [
    "factuur", "rekening", "nota", "bill", "invoice", 
    "belasting", "btw", "tax", "vat", "aanslag",
    "incasso", "aanmaning", "reminder", "overdue",
    "refund", "terugbetaling", "chargeback",
    "saldo", "afschrift", "account statement"
]

# Whitelist: emails or domains (lowercase). File lines or in-code list.
WHITELIST_FILE = "whitelist.txt"
WHITELIST = {  # you can also add here, e.g. "supplier@domain.com", "trusted.com"
    # "example@trusted.com", "trusted.com"
}

DRY_RUN = False   # <<< Set to False to actually move messages
VERBOSE = True

# =========================

def load_whitelist():
    items = set(w.strip().lower() for w in WHITELIST if w.strip())
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    items.add(line.lower())
    except FileNotFoundError:
        pass
    return items

def connect():
    m = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    m.login(USERNAME, PASSWORD)
    return m

def ensure_folder(m, mailbox):
    typ, data = m.list()
    if typ != "OK":
        return
    existing = [line.decode().split(' "/" ')[-1].strip('"') for line in data if line]
    if mailbox not in existing:
        m.create(mailbox)

def imap_date_before(days):
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%d-%b-%Y")  # e.g., 17-Sep-2025

def search_uids(m, folder, query_parts):
    m.select(folder, readonly=True)
    try:
        # Try the search with proper IMAP syntax
        if isinstance(query_parts, list):
            # Convert list to proper IMAP search string
            query_string = " ".join(str(part) for part in query_parts)
        else:
            query_string = query_parts
        
        typ, data = m.uid("SEARCH", None, query_string)
        if typ != "OK" or not data or data[0] is None:
            return set()
        uids = set(data[0].decode().split())
        return uids
    except Exception as e:
        if VERBOSE:
            print(f"[!] Search error: {e}")
        return set()

def union_searches(m, folder, queries):
    u = set()
    for q in queries:
        u |= search_uids(m, folder, q)
    return u

def fetch_headers(m, uid, fields="(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])"):
    typ, msg_data = m.uid("FETCH", uid, fields)
    if typ != "OK" or not msg_data or msg_data[0] is None:
        return None, None
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    subj = str(make_header(decode_header(msg.get("Subject", "")))).strip()
    from_raw = msg.get("From", "")
    return from_raw, subj

def parse_from_address(from_header):
    # crude but good-enough extraction of the email address
    addr = email.utils.parseaddr(from_header)[1].lower()
    domain = addr.split("@")[-1] if "@" in addr else ""
    return addr, domain

def uid_move(m, uid, dest):
    # Try UID MOVE (RFC 6851). If unsupported, fallback to COPY+DELETE.
    typ, _ = m.uid("MOVE", uid, dest)
    if typ == "OK":
        return True
    # Fallback
    typ, _ = m.uid("COPY", uid, dest)
    if typ != "OK":
        return False
    m.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
    m.expunge()
    return True

def main():
    wl = load_whitelist()
    if VERBOSE:
        print(f"[i] Loaded {len(wl)} whitelist entries")

    m = connect()
    if VERBOSE:
        print("[i] Logged in to iCloud IMAP")

    ensure_folder(m, TARGET_FOLDER)

    before = imap_date_before(AGE_DAYS)
    if VERBOSE:
        print(f"[i] Only touching messages BEFORE {before} (>{AGE_DAYS} days old)")

    # Build searches:
    # A) Messages with List-Unsubscribe header (unflagged and older than AGE_DAYS)
    q_list_unsub = f'NOT FLAGGED BEFORE {before} HEADER List-Unsubscribe ""'
    # B) Subject contains any keyword (we'll OR by running separate searches and union)
    subject_queries = [f'NOT FLAGGED BEFORE {before} SUBJECT "{kw}"' for kw in SUBJECT_KEYWORDS]

    total_candidates = 0
    total_moved = 0

    for folder in SOURCE_FOLDERS:
        try:
            m.select(folder, readonly=True)
        except Exception as e:
            print(f"[!] Could not select folder {folder}: {e}")
            continue

        set_a = search_uids(m, folder, q_list_unsub)
        set_b = union_searches(m, folder, subject_queries)
        candidates = list(set_a | set_b)

        if VERBOSE:
            print(f"[i] {folder}: {len(candidates)} candidate messages")

        for uid in candidates:
            from_raw, subject = fetch_headers(m, uid)
            if from_raw is None:
                continue
            addr, domain = parse_from_address(from_raw)

            # Whitelist check
            if addr in wl or domain in wl:
                if VERBOSE:
                    print(f"  - SKIP (whitelist): {addr} | {subject}")
                continue

            # Protect keywords (never move)
            subj_l = (subject or "").lower()
            if any(pk in subj_l for pk in PROTECT_KEYWORDS):
                if VERBOSE:
                    print(f"  - SKIP (protected subject): {subject}")
                continue

            total_candidates += 1

            if DRY_RUN:
                print(f"  - DRY-RUN would move UID {uid} from {folder} → {TARGET_FOLDER} | {addr} | {subject}")
            else:
                # Need writeable select to move
                m.select(folder)
                ok = uid_move(m, uid, TARGET_FOLDER)
                if ok:
                    total_moved += 1
                    if VERBOSE:
                        print(f"  - Moved UID {uid} to {TARGET_FOLDER}")
                else:
                    print(f"  - FAILED to move UID {uid}")

    print(f"[done] Candidates considered: {total_candidates}")
    if not DRY_RUN:
        print(f"[done] Actually moved:      {total_moved}")
    else:
        print("[note] DRY-RUN enabled — no changes were made. Set DRY_RUN=False to execute.")

if __name__ == "__main__":
    main()
