import re
from typing import List
from redactor.detectors import PIIDetector, PIISpan

_PLACE_NAMES = {
    "birdewadi", "chakan", "khed", "pune", "maharashtra", "mumbai", "india",
    "baner", "pallod", "montreal", "taloja", "padghe", "panvel", "raigad",
    "khalumbre", "supa", "ahilyanagar", "ahmednagar", "bandra", "kurla",
    "vikhroli", "bangalore", "delhi", "chennai", "kolkata", "hyderabad",
    "gujarat", "karnataka", "nagpur", "nashik", "thane", "andheri",
    "dadar", "parel", "mulund", "chembur", "sion", "wadala", "mahim",
    "khar", "santacruz", "vile parle", "juhu", "powai", "bhandup",
    "dombivli", "kalyan", "ambernath", "badlapur", "karjat", "lonavala",
    "hinjewadi", "wakad", "aundh", "kothrud", "kharadi", "hadapsar",
    "wanowrie", "koregaon park", "yerwada", "shivajinagar", "deccan",
    "navi", "belapur", "airoli", "ghansoli", "mahape", "rabale", "vashi",
    "kharghar", "seawoods", "nerul", "sanpada", "juinagar", "ulwe",
    "north", "south", "east", "west", "central", "upper", "lower",
    "floor", "colony", "society", "layout", "industrial", "zone",
    "village", "taluka", "tehsil", "district", "state", "city", "town",
    "farm", "plot", "sector", "block", "nagar", "panchayat",
}

_INSTITUTIONAL = {
    "limited", "private", "ltd", "pvt", "company", "corporation", "inc",
    "bank", "exchange", "securities", "board", "fund", "trust", "committee",
    "association", "council", "authority", "commission", "department",
    "ministry", "university", "college", "institute", "hospital", "clinic",
    "center", "estate", "international", "national", "global",
    "services", "solutions", "management", "consulting", "advisory",
    "analytics", "research", "bse", "nse", "sebi", "rbi", "roc", "llp",
    "icici", "hdfc", "mufg", "nuvama", "ksh", "offer", "directors",
    "promoters", "shareholder", "pursuant", "excludes", "reference",
    "managerial", "personnel", "secondary", "transfer", "selling",
    "pre", "post", "key", "executive", "non", "whole", "time",
    "equity", "share", "capital", "debenture", "warrant", "bonus",
    "rights", "issue", "allotment", "listing", "draft", "red", "herring",
    "prospectus", "sebi", "roc", "mca", "goi", "cin",
}

_STATUTORY_ORGS = {
    "sebi", "bse", "nse", "nsdl", "cdsl", "rbi", "roc", "goi",
    "securities and exchange board", "stock exchange", "bombay stock exchange",
    "national stock exchange", "reserve bank", "income tax", "mca",
    "ministry of corporate affairs", "registrar of companies",
}

_TITLE_PATTERN = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|Prof|Shri|Smt|Sri|Lt|Col|Maj|Gen|Cmdr)\.?\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})\b"
)

_KV_NAME_PATTERN = re.compile(
    r"(?:^|\b)Name\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})\b",
    re.MULTILINE,
)

_ALLCAPS_NAME = re.compile(r"\b([A-Z]{2,}(?:\s+[A-Z]{2,}){1,4})\b")

_ALLCAPS_STOP = {
    "PAN", "CIN", "DIN", "KYC", "RHP", "IPO", "BSE", "NSE", "SEBI",
    "NSDL", "CDSL", "ROC", "MCA", "RBI", "GOI", "AGM", "EGM", "FVCA",
    "ESOP", "ESPS", "QIB", "NII", "HNI", "RII", "ASBA", "UPI", "IMPS",
    "RTGS", "NEFT", "IFSC", "SWIFT", "INR", "USD", "EUR", "GBP",
    "EBITDA", "EBIT", "PAT", "PBT", "NAV", "NPA", "CAGR", "ROE", "ROA",
    "ROCE", "EPS", "P/E", "FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2",
    "INDIA", "MUMBAI", "PUNE", "DELHI", "LLC", "LLP", "PVT", "LTD",
    "PRIVATE", "LIMITED", "PUBLIC", "COMPANY", "CORPORATION", "INC",
    "PROMOTER", "DIRECTOR", "EXECUTIVE", "OFFICER", "CHAIRMAN", "CEO",
    "CFO", "CTO", "COO", "MD", "ED", "ID", "WTD",
    "OFFER", "SHARE", "EQUITY", "CAPITAL", "DEBENTURE", "PROSPECTUS",
    "DRAFT", "RED", "HERRING", "NOTE", "BOOK",
}


class NameDetector(PIIDetector):
    label = "PERSON"

    def __init__(self, nlp):
        self._nlp = nlp

    def detect(self, text: str) -> List[PIISpan]:
        out = []
        seen = set()

        def _add(start: int, end: int, text_: str, conf: float) -> None:
            key = (start, end)
            if key not in seen:
                seen.add(key)
                out.append(PIISpan(start, end, text_, self.label, conf))

        doc = self._nlp(text[:1_000_000])
        for ent in doc.ents:
            if ent.label_ != "PERSON":
                continue
            if not self._passes_filters(ent.text):
                continue
            _add(ent.start_char, ent.end_char, ent.text, 0.85)

        for m in _TITLE_PATTERN.finditer(text):
            name_part = m.group(2)
            if self._passes_filters(name_part):
                _add(m.start(), m.end(), m.group(), 0.90)

        for m in _KV_NAME_PATTERN.finditer(text):
            name_part = m.group(1)
            if self._passes_filters(name_part):
                _add(m.start(1), m.end(1), name_part, 0.80)

        for m in _ALLCAPS_NAME.finditer(text):
            tokens = m.group(1).split()
            if len(tokens) < 2:
                continue
            if any(t in _ALLCAPS_STOP for t in tokens):
                continue
            if any(len(t) < 3 for t in tokens):
                continue
            key = (m.start(), m.end())
            if key not in seen:
                seen.add(key)
                out.append(PIISpan(m.start(), m.end(), m.group(1), self.label, 0.70))

        return out

    @staticmethod
    def _passes_filters(name: str) -> bool:
        words = name.lower().split()
        if not words:
            return False
        if len(words) == 1 and len(words[0]) < 4:
            return False
        if any(w in _PLACE_NAMES for w in words):
            return False
        if any(w in _INSTITUTIONAL for w in words):
            return False
        if "family" in words and "trust" in words:
            return False
        return True


_COMPANY_SUFFIX = re.compile(
    r"\b[A-Z][a-zA-Z&\s]+(?:Limited|Ltd\.?|Private\s+Limited|LLP|LLC|"
    r"Inc\.?|Corporation|Corp\.?|PLC)\b"
)


class CompanyDetector(PIIDetector):
    label = "COMPANY"

    def __init__(self, nlp, enabled: bool = False):
        self._nlp = nlp
        self._enabled = enabled

    def detect(self, text: str) -> List[PIISpan]:
        if not self._enabled:
            return []
        out = []
        seen = set()

        def _add(s: int, e: int, t: str, c: float) -> None:
            if (s, e) not in seen:
                seen.add((s, e))
                out.append(PIISpan(s, e, t, self.label, c))

        doc = self._nlp(text[:1_000_000])
        for ent in doc.ents:
            if ent.label_ != "ORG":
                continue
            if any(st in ent.text.lower() for st in _STATUTORY_ORGS):
                continue
            _add(ent.start_char, ent.end_char, ent.text, 0.75)

        for m in _COMPANY_SUFFIX.finditer(text):
            if any(st in m.group().lower() for st in _STATUTORY_ORGS):
                continue
            _add(m.start(), m.end(), m.group(), 0.65)

        return out
