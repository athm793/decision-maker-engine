from __future__ import annotations

import re


_NEGATIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bassistant\b", re.IGNORECASE),
    re.compile(r"\bintern\b", re.IGNORECASE),
    re.compile(r"\bcoordinator\b", re.IGNORECASE),
    re.compile(r"\breceptionist\b", re.IGNORECASE),
    re.compile(r"\bclerk\b", re.IGNORECASE),
    re.compile(r"\btechnician\b", re.IGNORECASE),
    re.compile(r"\bsupport\b", re.IGNORECASE),
    re.compile(r"\bcustomer\s+service\b", re.IGNORECASE),
    re.compile(r"\brepresentative\b", re.IGNORECASE),
    re.compile(r"\bspecialist\b", re.IGNORECASE),
    re.compile(r"\bassociate\b", re.IGNORECASE),
    re.compile(r"\bstaff\b", re.IGNORECASE),
]

_POSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("CEO", re.compile(r"\bCEO\b|\bChief\s+Executive\s+Officer\b", re.IGNORECASE)),
    ("COO", re.compile(r"\bCOO\b|\bChief\s+Operating\s+Officer\b", re.IGNORECASE)),
    ("CFO", re.compile(r"\bCFO\b|\bChief\s+Financial\s+Officer\b", re.IGNORECASE)),
    ("CTO", re.compile(r"\bCTO\b|\bChief\s+Technology\s+Officer\b", re.IGNORECASE)),
    ("CIO", re.compile(r"\bCIO\b|\bChief\s+Information\s+Officer\b", re.IGNORECASE)),
    ("CMO", re.compile(r"\bCMO\b|\bChief\s+Marketing\s+Officer\b", re.IGNORECASE)),
    ("Chief", re.compile(r"\bChief\b", re.IGNORECASE)),
    ("Founder", re.compile(r"\bco[- ]?founder\b|\bfounder\b", re.IGNORECASE)),
    ("Owner", re.compile(r"\bowner\b", re.IGNORECASE)),
    ("President", re.compile(r"\bpresident\b", re.IGNORECASE)),
    ("Managing Director", re.compile(r"\bmanaging\s+director\b", re.IGNORECASE)),
    ("General Manager", re.compile(r"\bgeneral\s+manager\b", re.IGNORECASE)),
    ("Senior Head", re.compile(r"\bsenior\s+head\b", re.IGNORECASE)),
    ("Head", re.compile(r"\bhead\b|\bhead\s+of\b", re.IGNORECASE)),
    ("Senior Director", re.compile(r"\bsenior\s+director\b", re.IGNORECASE)),
    ("Director", re.compile(r"\bdirector\b", re.IGNORECASE)),
    ("Senior Vice President", re.compile(r"\bsenior\s+vice\s+president\b|\bSVP\b", re.IGNORECASE)),
    ("Vice President", re.compile(r"\bvice\s+president\b|\bVP\b", re.IGNORECASE)),
    ("Chairman", re.compile(r"\bchairman\b|\bchair\b", re.IGNORECASE)),
    ("Managing Partner", re.compile(r"\bmanaging\s+partner\b", re.IGNORECASE)),
    ("Managing Member", re.compile(r"\bmanaging\s+member\b", re.IGNORECASE)),
    ("Partner", re.compile(r"\bpartner\b", re.IGNORECASE)),
    ("Principal", re.compile(r"\bprincipal\b", re.IGNORECASE)),
]


def is_decision_maker_title(title: str | None) -> tuple[bool, str]:
    t = (title or "").strip()
    if not t:
        return (False, "")

    for rx in _NEGATIVE_PATTERNS:
        if rx.search(t):
            return (False, "")

    for keyword, rx in _POSITIVE_PATTERNS:
        if rx.search(t):
            return (True, keyword)

    return (False, "")


def decision_maker_query_keywords() -> list[str]:
    return [
        "CEO",
        "Founder",
        "\"Co-Founder\"",
        "Owner",
        "President",
        "\"Managing Director\"",
        "\"General Manager\"",
        "\"Senior Head\"",
        "\"Head of\"",
        "\"Senior Director\"",
        "Director",
        "\"Senior Vice President\"",
        "\"Vice President\"",
        "SVP",
        "VP",
        "COO",
        "CFO",
        "CTO",
        "CIO",
        "CMO",
        "Partner",
        "Principal",
        "\"Managing Partner\"",
        "\"Managing Member\"",
        "Chairman",
    ]

