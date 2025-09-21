"""
Email analysis and decision making logic.

Provides pure functions for analyzing emails and determining processing actions
without any I/O operations.
"""

import email.utils
from typing import List, Set, Tuple, Optional


class EmailAnalyzer:
    """Analyzes emails and makes processing decisions."""

    def __init__(self, whitelist: Set[str], protect_keywords: List[str],
                 subject_keywords: List[str], delete_domains: List[str]):
        """Initialize email analyzer.

        Args:
            whitelist: Set of whitelisted email addresses and domains
            protect_keywords: Keywords that protect emails from processing
            subject_keywords: Keywords in subject that trigger processing
            delete_domains: Domains that trigger processing
        """
        self.whitelist = whitelist
        self.protect_keywords = protect_keywords
        self.subject_keywords = subject_keywords
        self.delete_domains = delete_domains

    def parse_from_address(self, from_header: str) -> Tuple[str, str]:
        """Extract email address and domain from From header.

        Args:
            from_header: Raw From header value

        Returns:
            Tuple of (email_address, domain)
        """
        addr = email.utils.parseaddr(from_header)[1].lower()
        domain = addr.split("@")[-1] if "@" in addr else ""
        return addr, domain

    def should_process_email(self, uid: str, from_raw: Optional[str], subject: Optional[str],
                           set_a: Set[str], set_b: Set[str], set_c: Set[str]) -> Optional[Tuple[str, str, str, str]]:
        """Determine if an email should be processed and why.

        Args:
            uid: Email UID
            from_raw: Raw From header
            subject: Email subject
            set_a: Set of UIDs matching List-Unsubscribe criteria
            set_b: Set of UIDs matching subject keyword criteria
            set_c: Set of UIDs matching delete domain criteria

        Returns:
            Tuple of (action, reason, address, subject) or None if no processing needed
            Action is either "skip" or "process"
        """
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
        match_reason = self._determine_match_reason(uid, subj_lower, domain, addr, set_a, set_b, set_c)

        return ("process", match_reason, addr, subject or "")

    def _determine_match_reason(self, uid: str, subj_lower: str, domain: str, addr: str,
                               set_a: Set[str], set_b: Set[str], set_c: Set[str]) -> str:
        """Determine why an email matched processing criteria.

        Args:
            uid: Email UID
            subj_lower: Lowercase subject
            domain: Email domain
            addr: Email address
            set_a: List-Unsubscribe matches
            set_b: Subject keyword matches
            set_c: Delete domain matches

        Returns:
            Human-readable reason for processing
        """
        if uid in set_a:
            return "List-Unsubscribe header"
        elif uid in set_b:
            # Find which keyword matched
            for kw in self.subject_keywords:
                if kw.lower() in subj_lower:
                    return f"subject keyword '{kw}'"
            return "subject keyword"
        elif uid in set_c:
            # Find which domain matched
            for del_domain in self.delete_domains:
                if domain == del_domain or addr.endswith(f"@{del_domain}"):
                    return f"delete domain '{del_domain}'"
            return "delete domain"

        return "unknown"

    def is_whitelisted(self, from_header: str) -> bool:
        """Check if an email address or domain is whitelisted.

        Args:
            from_header: Raw From header value

        Returns:
            True if whitelisted, False otherwise
        """
        addr, domain = self.parse_from_address(from_header)
        return addr in self.whitelist or domain in self.whitelist

    def is_protected(self, subject: str) -> bool:
        """Check if an email subject contains protected keywords.

        Args:
            subject: Email subject

        Returns:
            True if protected, False otherwise
        """
        subj_lower = subject.lower()
        return any(pk in subj_lower for pk in self.protect_keywords)

    def get_protection_status(self, from_header: str, subject: str) -> Tuple[bool, str]:
        """Get comprehensive protection status for an email.

        Args:
            from_header: Raw From header value
            subject: Email subject

        Returns:
            Tuple of (is_protected, reason)
        """
        if self.is_whitelisted(from_header):
            return (True, "whitelisted sender")

        if self.is_protected(subject):
            return (True, "protected keywords in subject")

        return (False, "not protected")