import re
from dataclasses import dataclass
from typing import List, Iterator

@dataclass
class PIISpan:
    start: int
    end: int
    text: str
    label: str
    confidence: float = 1.0


class PIIDetector:
    label: str = "UNKNOWN"

    def detect(self, text: str) -> List[PIISpan]:
        raise NotImplementedError


class RegexDetector(PIIDetector):
    def __init__(self, pattern: str, label: str, flags: int = re.IGNORECASE, confidence: float = 1.0):
        self._re = re.compile(pattern, flags)
        self.label = label
        self._conf = confidence

    def detect(self, text: str) -> List[PIISpan]:
        return [
            PIISpan(m.start(), m.end(), m.group(), self.label, self._conf)
            for m in self._re.finditer(text)
        ]


class EmailDetector(RegexDetector):
    _SKIP = re.compile(r"\.(jpeg|png|jpg|gif|pdf|docx|xlsx|pptx)$", re.I)

    def __init__(self):
        super().__init__(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "EMAIL")

    def detect(self, text: str) -> List[PIISpan]:
        return [e for e in super().detect(text) if not self._SKIP.search(e.text)]


class PhoneDetector(PIIDetector):
    label = "PHONE"
    _PATTERNS = [
        r"\+91[\s\-]?\d{5}[\s\-]?\d{5}",
        r"\+91[\s\-]?\d{3,5}[\s\-]?\d{5,7}",
        r"\b0\d{10}\b",
        r"\b[6-9]\d{4}[\s\-]?\d{5}\b",
    ]

    def detect(self, text: str) -> List[PIISpan]:
        seen = set()
        out = []
        for pat in self._PATTERNS:
            for m in re.finditer(pat, text):
                key = (m.start(), m.end())
                if key in seen:
                    continue
                digits = re.sub(r"\D", "", m.group())
                if digits.startswith("91"):
                    digits = digits[2:]
                if len(digits) != 10:
                    continue
                seen.add(key)
                out.append(PIISpan(m.start(), m.end(), m.group(), self.label))
        return out


class IPDetector(RegexDetector):
    def __init__(self):
        super().__init__(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP_ADDRESS")

    def detect(self, text: str) -> List[PIISpan]:
        out = []
        for span in super().detect(text):
            octets = span.text.split(".")
            if all(0 <= int(o) <= 255 for o in octets):
                out.append(span)
        return out


class SSNDetector(RegexDetector):
    def __init__(self):
        super().__init__(r"\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b", "SSN")

    def detect(self, text: str) -> List[PIISpan]:
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


class CreditCardDetector(PIIDetector):
    label = "CREDIT_CARD"
    _PATTERN = re.compile(
        r"\b(?:"
        r"4\d{3}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}"
        r"|5[1-5]\d{2}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}"
        r"|3[47]\d{2}[\s\-]?\d{6}[\s\-]?\d{5}"
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

    def detect(self, text: str) -> List[PIISpan]:
        out = []
        for m in self._PATTERN.finditer(text):
            d = re.sub(r"\D", "", m.group())
            if len(d) >= 13 and self._luhn(d):
                out.append(PIISpan(m.start(), m.end(), m.group(), self.label))
        return out


class DOBDetector(PIIDetector):
    label = "DOB"
    _INDICATORS = re.compile(r"\b(date\s+of\s+birth|d\.?o\.?b\.?|born\s+on|birth\s+date|dob)\b", re.I)
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
    _WINDOW = 120

    def detect(self, text: str) -> List[PIISpan]:
        found = {}
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
                        found[key] = PIISpan(abs_start, abs_end, dm.group(), self.label)
        return list(found.values())


class PANDetector(RegexDetector):
    def __init__(self):
        super().__init__(r"\b[A-Z]{5}\d{4}[A-Z]\b", "PAN", flags=0)


class CINDetector(RegexDetector):
    def __init__(self):
        super().__init__(r"\b[A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b", "CIN", flags=0)


def all_structured_detectors() -> List[PIIDetector]:
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
