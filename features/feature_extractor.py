# File: features/feature_extractor.py
# Shared feature extractor used by prepare scripts AND predict.py at runtime.
# Extracts identical numerical features from both CSV rows and real parsed emails.

import re
import html
from typing import Dict


# ── Domain Trust Registry ──────────────────────────────────────────────────────
# Loaded from trusted_domains.json in the same directory as this file.
# To add/remove domains — edit trusted_domains.json, no code change needed.
import json as _json
import pathlib as _pathlib

def _load_trusted_domains() -> dict:
    json_path = _pathlib.Path(__file__).parent / 'trusted_domains.json'
    if json_path.exists():
        with open(json_path, 'r') as _f:
            return _json.load(_f)
    # Fallback minimal list if JSON not found
    return {
        'google.com': 0.95, 'microsoft.com': 0.95, 'apple.com': 0.95,
        'gmail.com': 0.9, 'outlook.com': 0.85, 'yahoo.com': 0.8,
        'amazon.com': 0.92, 'github.com': 0.9,
    }

TRUSTED_DOMAINS = _load_trusted_domains()

URGENT_WORDS = [
    'urgent', 'immediately', 'action required', 'suspended', 'verify now',
    'account locked', 'limited time', 'expires', 'deadline', 'act now',
    'respond immediately', 'within 24 hours', 'within 48 hours',
    'last chance', 'final notice', 'warning', 'alert'
]

SPAM_WORDS = [
    'free', 'winner', 'cash', 'prize', 'win', 'bonus', 'reward',
    'congratulations', 'selected', 'click here', 'buy now', 'order now',
    'discount', 'offer', 'sale', 'deal', 'cheap', 'save money',
    'make money', 'earn money', 'million', 'billion', 'guarantee'
]

PHISHING_WORDS = [
    'verify', 'verification', 'password', 'login', 'confirm', 'update your',
    'account suspended', 'unusual activity', 'security alert', 'click here',
    'enter your', 'provide your', 'validate', 'reactivate', 'unauthorized',
    'compromised', 'reset your password', 'identity', 'credentials'
]

OTP_KEYWORDS = [
    'otp', 'one-time', 'one time password', 'verification code',
    'security code', 'authentication code', 'access code', 'pin',
    '2fa', 'two-factor', 'two factor', 'confirm your', 'confirmation code'
]

URL_PATTERN = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
    re.IGNORECASE
)

OTP_CODE_PATTERN = re.compile(r'\b\d{4,8}\b|\b[A-Z0-9]{4,8}\b')


def get_sender_reputation(sender_domain: str) -> float:
    """Return trust score for a sender domain."""
    if not sender_domain:
        return 0.3
    domain = sender_domain.lower().strip()
    if domain in TRUSTED_DOMAINS:
        return TRUSTED_DOMAINS[domain]
    # Check if it's a subdomain of a trusted domain
    for trusted, score in TRUSTED_DOMAINS.items():
        if domain.endswith('.' + trusted):
            return score * 0.95
    # Unknown domain — low trust
    return 0.3


def extract_features_from_text(
    subject: str,
    body: str,
    sender_domain: str = '',
    num_attachments: int = 0,
    is_reply: bool = False,
    is_forward: bool = False,
    hour: int = 12,
    day_of_week: int = 0
) -> Dict:
    """
    Extract numerical features from raw email text.
    This is called at RUNTIME in predict.py on real parsed emails.
    Returns a dict with exactly the same keys as the training CSV features.
    """
    # Decode HTML entities
    body = html.unescape(str(body or ''))
    subject = html.unescape(str(subject or ''))
    combined = (subject + ' ' + body).lower()

    # ── Link features ──────────────────────────────────────────
    urls = URL_PATTERN.findall(body)
    num_links = len(urls)

    # ── HTML detection ─────────────────────────────────────────
    contains_html = 1 if re.search(r'<[a-zA-Z][^>]*>', body) else 0

    # ── Text length ────────────────────────────────────────────
    email_length = len(body)

    # ── Punctuation / casing ───────────────────────────────────
    num_exclamations = body.count('!')
    words = body.split()
    num_uppercase_words = sum(1 for w in words if w.isupper() and len(w) > 1)

    # ── Keyword signals ────────────────────────────────────────
    has_urgent_words = 1 if any(w in combined for w in URGENT_WORDS) else 0
    has_spam_words = 1 if any(w in combined for w in SPAM_WORDS) else 0
    has_phishing_words = 1 if any(w in combined for w in PHISHING_WORDS) else 0

    
    # ── OTP detection ──────────────────────────────────────────
    contains_otp = 0
    subject_lower = subject.lower()
    body_start = body[:500].lower()

# If OTP keyword is in the SUBJECT — that's enough, no code needed
    if any(kw in subject_lower for kw in OTP_KEYWORDS):
        contains_otp = 1
# If OTP keyword is in first 500 chars of body + code exists anywhere
    elif any(kw in body_start for kw in OTP_KEYWORDS):
        if OTP_CODE_PATTERN.search(body[:500]):
            contains_otp = 1

    # ── Sender reputation ──────────────────────────────────────
    sender_reputation = get_sender_reputation(sender_domain)

    # ── Reply / forward ────────────────────────────────────────
    subject_lower = subject.lower().strip()
    if not is_reply:
        is_reply = 1 if subject_lower.startswith('re:') else 0
    if not is_forward:
        is_forward = 1 if subject_lower.startswith(('fwd:', 'fw:')) else 0

    return {
        'num_links': num_links,
        'num_attachments': int(num_attachments),
        'has_urgent_words': has_urgent_words,
        'has_spam_words': has_spam_words,
        'has_phishing_words': has_phishing_words,
        'contains_html': contains_html,
        'email_length': min(email_length, 10000),  # cap outliers
        'num_exclamations': num_exclamations,
        'num_uppercase_words': num_uppercase_words,
        'day_of_week': int(day_of_week),
        'hour': int(hour),
        'is_reply': int(is_reply),
        'is_forward': int(is_forward),
        'sender_reputation': sender_reputation,
        'contains_otp': contains_otp,
    }


def extract_features_from_csv_row(row) -> Dict:
    """
    Extract features directly from a CSV row (synthetic dataset).
    The CSV already has pre-computed features — we just select and normalise them.
    Used only during prepare_*.py scripts (training data preparation).
    """
    subject = str(row.get('subject', ''))
    body = str(row.get('body', ''))
    combined = (subject + ' ' + body).lower()

    # Use pre-computed CSV columns where available
    # Fall back to computing from text where not
    num_links = int(row.get('num_links', 0))
    num_attachments = int(row.get('num_attachments', 0))
    has_urgent_words = int(row.get('has_urgent_words', 0))
    has_spam_words = int(row.get('has_spam_words', 0))
    has_phishing_words = int(row.get('has_phishing_words', 0))
    contains_html = int(row.get('contains_html', 0))
    email_length = min(int(row.get('email_length', len(body))), 10000)
    num_exclamations = int(row.get('num_exclamations', 0))
    num_uppercase_words = int(row.get('num_uppercase_words', 0))
    day_of_week = int(row.get('day_of_week', 0))
    hour = int(row.get('hour', 12))
    is_reply = int(row.get('is_reply', 0))
    is_forward = int(row.get('is_forward', 0))
    sender_domain = str(row.get('sender_domain', ''))
    sender_reputation = float(row.get('sender_reputation',
                                      get_sender_reputation(sender_domain)))

    # OTP — not in CSV so we compute it
    contains_otp = 0
    if any(kw in combined for kw in OTP_KEYWORDS):
        if OTP_CODE_PATTERN.search(combined):
            contains_otp = 1

    return {
        'num_links': num_links,
        'num_attachments': num_attachments,
        'has_urgent_words': has_urgent_words,
        'has_spam_words': has_spam_words,
        'has_phishing_words': has_phishing_words,
        'contains_html': contains_html,
        'email_length': email_length,
        'num_exclamations': num_exclamations,
        'num_uppercase_words': num_uppercase_words,
        'day_of_week': day_of_week,
        'hour': hour,
        'is_reply': is_reply,
        'is_forward': is_forward,
        'sender_reputation': sender_reputation,
        'contains_otp': contains_otp,
    }


# The exact feature column order used for training.
# predict.py must produce features in this same order.
FEATURE_COLUMNS = [
    'num_links',
    'num_attachments',
    'has_urgent_words',
    'has_spam_words',
    'has_phishing_words',
    'contains_html',
    'email_length',
    'num_exclamations',
    'num_uppercase_words',
    'day_of_week',
    'hour',
    'is_reply',
    'is_forward',
    'sender_reputation',
    'contains_otp',
]