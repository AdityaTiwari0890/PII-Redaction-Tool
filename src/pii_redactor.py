import re
import hashlib
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import List, Tuple, Dict
from copy import deepcopy

import spacy
from faker import Faker
from docx import Document

class DeterministicFaker:
    """Same source entity always receives the same synthetic replacement."""
    
    def __init__(self, seed: int = 42):
        self._cache: Dict[Tuple[str, str], str] = {}
        self._fake = Faker('en_IN')
        self._fake.seed_instance(seed)
        
        # Pre-generate pools for consistency across runs
        self._pools = {
            "PERSON": [self._fake.name() for _ in range(500)],
            "EMAIL": [self._fake.email() for _ in range(500)],
            "PHONE": [f"+91 {self._fake.msisdn()[3:]}" for _ in range(200)],
            "COMPANY": [self._fake.company() for _ in range(200)],
            "ADDRESS": [self._fake.address().replace('\n', ', ') for _ in range(200)],
            "SSN": [self._fake.ssn() for _ in range(100)],
            "CREDIT_CARD": [self._fake.credit_card_number(card_type='visa') for _ in range(100)],
            "DOB": [self._fake.date_of_birth(minimum_age=25, maximum_age=65).strftime("%B %d, %Y") for _ in range(100)],
            "IP_ADDRESS": [self._fake.ipv4() for _ in range(100)],
            "PAN": [self._fake.bothify(text="?????#####?", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(100)],
            "CIN": [self._fake.bothify(text="U#####??####PLC######", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(100)],
        }
    
    def get(self, original: str, label: str) -> str:
        key = (original, label)
        if key not in self._cache:
            pool = self._pools.get(label, ["[REDACTED]"])
            idx = int(hashlib.md5((original + label).encode()).hexdigest(), 16) % len(pool)
            self._cache[key] = pool[idx]
        return self._cache[key]
    
@dataclass
class PIIEntity:
    start: int
    end: int
    text: str
    label: str
    confidence: float = 1.0


class PIIDetector:
    def detect(self, text: str) -> List[PIIIEntity]:
        raise NotImplementedError


class RegexDetector(PIIDetector):
    def __init__(self, pattern: str, label: str, flags=re.IGNORECASE):
        self.pattern = re.compile(pattern, flags)
        self.label = label
    
    def detect(self, text: str) -> List[PIIEntity]:
        return [PIIEntity(m.start(), m.end(), m.group(), self.label) 
                for m in self.pattern.finditer(text)]


class EmailDetector(RegexDetector):
    def __init__(self):
        super().__init__(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "EMAIL")
    
    def detect(self, text: str) -> List[PIIEntity]:
        ents = super().detect(text)
        # Filter out image filenames
        return [e for e in ents if not re.search(r'\.(jpeg|png|jpg|gif|pdf|docx)$', e.text, re.I)]


class PhoneDetector(PIIDetector):
    PATTERNS = [
        r'\+91\s*\d{2,5}\s*\d{5,8}',           # +91 22 4009 4400
        r'\+91\s*\d{5}\s*\d{5}',                # +91 81081 14949
        r'\b\d{5}\s*\d{5}\b',                   # 81081 14949
    ]
    
    def detect(self, text: str) -> List[PIIEntity]:
        seen, out = set(), []
        for p in self.PATTERNS:
            for m in re.finditer(p, text):
                key = (m.start(), m.end())
                if key not in seen:
                    seen.add(key)
                    out.append(PIIEntity(m.start(), m.end(), m.group(), "PHONE"))
        return out


class IPDetector(RegexDetector):
    def __init__(self):
        ipv4 = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        super().__init__(ipv4, "IP_ADDRESS")


class SSNDetector(RegexDetector):
    def __init__(self):
        super().__init__(r'\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b', "SSN")
    
    def detect(self, text: str) -> List[PIIEntity]:
        ents = super().detect(text)
        filtered = []
        for e in ents:
            digits = re.sub(r'\D', '', e.text)
            if len(digits) != 9:
                continue
            # Basic SSN validation (exclude 000, 666 prefixes, 9xx, etc.)
            if (digits.startswith('000') or digits.startswith('666') or 
                digits[0] == '9' or digits[3:5] == '00' or digits[5:] == '0000'):
                continue
            filtered.append(e)
        return filtered


class CreditCardDetector(RegexDetector):
    def __init__(self):
        pattern = (r'\b(?:4\d{3}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}|'
                   r'5[1-5]\d{2}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}|'
                   r'3[47]\d{2}[\s\-]?\d{6}[\s\-]?\d{5})\b')
        super().__init__(pattern, "CREDIT_CARD")
    
    def _luhn(self, digits: str) -> bool:
        total = 0
        for i, d in enumerate(digits[::-1]):
            n = int(d)
            if i % 2 == 1:
                n *= 2
                if n > 9: n -= 9
            total += n
        return total % 10 == 0
    
    def detect(self, text: str) -> List[PIIEntity]:
        ents = super().detect(text)
        out = []
        for e in ents:
            d = re.sub(r'\D', '', e.text)
            if len(d) >= 13 and self._luhn(d):
                out.append(e)
        return out


class DOBDetector(PIIDetector):
    INDICATORS = re.compile(r'\b(date of birth|d\.?o\.?b\.?|born on|birth date)\b', re.I)
    DATE_PATS = [
        re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
        re.compile(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b', re.I),
    ]
    
    def detect(self, text: str) -> List[PIIEntity]:
        out = []
        for m in self.INDICATORS.finditer(text):
            start_ctx = max(0, m.start() - 80)
            end_ctx = min(len(text), m.end() + 80)
            window = text[start_ctx:end_ctx]
            for pat in self.DATE_PATS:
                for dm in pat.finditer(window):
                    out.append(PIIEntity(start_ctx + dm.start(), start_ctx + dm.end(), dm.group(), "DOB"))
        return out


class PANDetector(RegexDetector):
    def __init__(self):
        super().__init__(r'\b[A-Z]{5}\d{4}[A-Z]\b', "PAN")


class CINDetector(RegexDetector):
    def __init__(self):
        super().__init__(r'\b[A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b', "CIN")

