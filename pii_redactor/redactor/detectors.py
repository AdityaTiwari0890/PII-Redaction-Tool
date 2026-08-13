"""
detectors.py
============
Regex + validated detectors for all structured PII types.

Each detector is a standalone class with a single public method:
    detect(text: str) -> list[PIISpan]

PIISpan is a lightweight dataclass: (start, end, text, label, confidence).

Extending:
    Add a new class inheriting RegexDetector (or PIIDetector for custom logic),
    set its label, and register it in pipeline.py → PIIPipeline.detectors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PIISpan:
    start: int
    end: int
    text: str
    label: str
    confidence: float = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Base classes
# ─────────────────────────────────────────────────────────────────────────────


class PIIDetector:
    """Abstract base – all detectors implement detect()."""

    label: str = "UNKNOWN"

    def detect(self, text: str) -> list[PIISpan]:  # pragma: no cover
        raise NotImplementedError


class RegexDetector(PIIDetector):
    """Detect PII via a single compiled regex."""

    def __init__(
        self,
        pattern: str,
        label: str,
        flags: int = re.IGNORECASE,
        confidence: float = 1.0,
    ) -> None:
        self._re = re.compile(pattern, flags)
        self.label = label
        self._conf = confidence

    def _iter_matches(self, text: str) -> Iterator[re.Match]:
        return self._re.finditer(text)

    def detect(self, text: str) -> list[PIISpan]:
        return [
            PIISpan(m.start(), m.end(), m.group(), self.label, self._conf)
            for m in self._iter_matches(text)
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Structured PII detectors
# ─────────────────────────────────────────────────────────────────────────────


class EmailDetector(RegexDetector):
    """Detects e-mail addresses; excludes image/document filenames."""

    _SKIP = re.compile(r"\.(jpeg|png|jpg|gif|pdf|docx|xlsx|pptx)$", re.I)

    def __init__(self) -> None:
        super().__init__(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
            "EMAIL",
        )

    def detect(self, text: str) -> list[PIISpan]:
        return [e for e in super().detect(text) if not self._SKIP.search(e.text)]


# ─────────────────────────────────────────────────────────────────────────────


class PhoneDetector(PIIDetector):
    """
    Detects Indian phone numbers in multiple formats.
    Validates digit-count (10 digits, optionally prefixed by +91/0).
    """

    label = "PHONE"

    _PATTERNS = [
        # +91 followed by 10 digits (with optional spaces/dashes)
        r"\+91[\s\-]?\d{5}[\s\-]?\d{5}",
        r"\+91[\s\-]?\d{3,5}[\s\-]?\d{5,7}",
        # 0 then 10 digits
        r"\b0\d{10}\b",
        # bare 10-digit number (word boundary protected)
        r"\b[6-9]\d{4}[\s\-]?\d{5}\b",
    ]

    def detect(self, text: str) -> list[PIISpan]:
        seen: set[tuple[int, int]] = set()
        out: list[PIISpan] = []
        for pat in self._PATTERNS:
            for m in re.finditer(pat, text):
                key = (m.start(), m.end())
                if key in seen:
                    continue
                # Validate: strip non-digits, must be 10 or 12 digits (with 91)
                digits = re.sub(r"\D", "", m.group())
                if digits.startswith("91"):
                    digits = digits[2:]
                if len(digits) != 10:
                    continue
                seen.add(key)
                out.append(PIISpan(m.start(), m.end(), m.group(), self.label))
        return out


# ─────────────────────────────────────────────────────────────────────────────


class IPDetector(RegexDetector):
    """Detects valid IPv4 addresses with octet-range validation."""

    def __init__(self) -> None:
        # Looser pattern, then validated below
        super().__init__(
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            "IP_ADDRESS",
        )

    def detect(self, text: str) -> list[PIISpan]:
        out = []
        for span in super().detect(text):
            octets = span.text.split(".")
            if all(0 <= int(o) <= 255 for o in octets):
                out.append(span)
        return out


# ─────────────────────────────────────────────────────────────────────────────


class SSNDetector(RegexDetector):
    """
    US-style SSN: NNN-NN-NNNN or NNN NN NNNN or NNNNNNNNN.
    Validates: not 000/666/9xx area, non-zero group & serial.
    These are rare/absent in Indian RHP but included per spec.
    """

    def __init__(self) -> None:
        super().__init__(
            r"\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b",
            "SSN",
        )

    def detect(self, text: str) -> list[PIISpan]:
        out = []
        for span in super().detect(text):
            d = re.sub(r"\D", "", span.text)
            if len(d) != 9:
                continue
            area, group, serial = d[:3], d[3:5], d[5:]
            if area in ("000", "666") or area.startswith("9"):
                continue
            if group == "00" or serial == "0000":
                continue
            out.append(span)
        return out


# ─────────────────────────────────────────────────────────────────────────────


class CreditCardDetector(PIIDetector):
    """
    Detects major card formats (Visa 16, MC 16, Amex 15).
    Validates via Luhn checksum to eliminate false positives.
    """

    label = "CREDIT_CARD"

    _PATTERN = re.compile(
        r"\b(?:"
        r"4\d{3}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}"  # Visa 16
        r"|5[1-5]\d{2}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}"  # MC 16
        r"|3[47]\d{2}[\s\-]?\d{6}[\s\-]?\d{5}"  # Amex 15
        r")\b"
    )

    @staticmethod
    def _luhn(digits: str) -> bool:
        total = 0
        for i, ch in enumerate(reversed(digits)):
            n = int(ch)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0

    def detect(self, text: str) -> list[PIISpan]:
        out = []
        for m in self._PATTERN.finditer(text):
            d = re.sub(r"\D", "", m.group())
            if len(d) >= 13 and self._luhn(d):
                out.append(PIISpan(m.start(), m.end(), m.group(), self.label))
        return out


# ─────────────────────────────────────────────────────────────────────────────


class DOBDetector(PIIDetector):
    """
    Detects dates-of-birth using context-window heuristic:
    only flags dates within ±100 chars of a DOB keyword.
    """

    label = "DOB"

    _INDICATORS = re.compile(
        r"\b(date\s+of\s+birth|d\.?o\.?b\.?|born\s+on|birth\s+date|dob)\b",
        re.I,
    )
    _DATE_PATTERNS = [
        re.compile(r"\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b"),
        re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|"
            r"September|October|November|December|"
            r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
            r"\s+\d{1,2},?\s+\d{4}\b",
            re.I,
        ),
        re.compile(
            r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)\s+\d{4}\b",
            re.I,
        ),
    ]

    _WINDOW = 120  # characters on each side of indicator

    def detect(self, text: str) -> list[PIISpan]:
        found: dict[tuple[int, int], PIISpan] = {}
        for ind in self._INDICATORS.finditer(text):
            lo = max(0, ind.start() - self._WINDOW)
            hi = min(len(text), ind.end() + self._WINDOW)
            window = text[lo:hi]
            for pat in self._DATE_PATTERNS:
                for dm in pat.finditer(window):
                    abs_start = lo + dm.start()
                    abs_end = lo + dm.end()
                    key = (abs_start, abs_end)
                    if key not in found:
                        found[key] = PIISpan(
                            abs_start, abs_end, dm.group(), self.label
                        )
        return list(found.values())


# ─────────────────────────────────────────────────────────────────────────────


class PANDetector(RegexDetector):
    """Indian PAN: 5 letters + 4 digits + 1 letter (e.g. ABCDE1234F)."""

    def __init__(self) -> None:
        super().__init__(r"\b[A-Z]{5}\d{4}[A-Z]\b", "PAN", flags=0)


# ─────────────────────────────────────────────────────────────────────────────


class CINDetector(RegexDetector):
    """
    Corporate Identification Number (CIN) of Indian companies.
    Format: U12345AB1234PLC123456
    """

    def __init__(self) -> None:
        super().__init__(
            r"\b[A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b",
            "CIN",
            flags=0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: all structured detectors in priority order
# ─────────────────────────────────────────────────────────────────────────────


def all_structured_detectors() -> list[PIIDetector]:
    """Return all regex/validated detectors, highest-priority first."""
    return [
        EmailDetector(),
        PhoneDetector(),
        PANDetector(),
        CINDetector(),
        IPDetector(),
        SSNDetector(),
        CreditCardDetector(),
        DOBDetector(),
    ]
