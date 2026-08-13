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


class NameDetector(PIIDetector):
    """
    spaCy NER for PERSON with aggressive false-positive filtering.
    """
    
    PLACE_NAMES = {
        'birdewadi', 'chakan', 'khed', 'pune', 'maharashtra', 'mumbai', 'india',
        'baner', 'pallod', 'montreal', 'taloja', 'padghe', 'panvel', 'raigad',
        'khalumbre', 'supa', 'ahilyanagar', 'ahmednagar', 'bandra', 'kurla',
        'vikhroli', 'bangalore', 'delhi', 'chennai', 'kolkata', 'hyderabad',
        'gujarat', 'karnataka', 'nagpur', 'nashik', 'thane', 'andheri',
        'dadar', 'parel', 'mulund', 'chembur', 'sion', 'wadala', 'mahim',
        'khar', 'santacruz', 'vile parle', 'juhu', 'powai', 'bhandup',
        'dombivli', 'kalyan', 'ambernath', 'badlapur', 'karjat', 'lonavala',
        'hinjewadi', 'wakad', 'aundh', 'kothrud', 'kharadi', 'hadapsar',
        'wanowrie', 'koregaon park', 'yerwada', 'shivajinagar', 'deccan',
        'mg road', 'laxmi road', 'budhwar peth', 'ravivar peth', 'nagar',
        'colony', 'society', 'layout', 'park', 'industrial', 'area', 'zone',
        'road', 'street', 'lane', 'avenue', 'highway', 'expressway',
        'east', 'west', 'north', 'south', 'central', 'upper', 'lower',
        'floor', 'tower', 'building', 'complex', 'plaza', 'mall', 'centre',
        'farm', 'farms', 'business', 'office', 'plot', 'sector', 'block',
        'village', 'taluka', 'taluk', 'tehsil', 'district', 'state', 'country',
        'city', 'town', 'municipality', 'panchayat',
    }
    
    INSTITUTIONAL = {
        'limited', 'private', 'ltd', 'pvt', 'company', 'corporation', 'inc',
        'bank', 'exchange', 'securities', 'board', 'fund', 'trust', 'committee',
        'association', 'council', 'authority', 'commission', 'department',
        'ministry', 'university', 'college', 'institute', 'hospital', 'clinic',
        'center', 'estate', 'international', 'national', 'global',
        'services', 'solutions', 'management', 'consulting', 'advisory',
        'analytics', 'research', 'bse', 'nse', 'sebi', 'rbi', 'roc', 'llp',
        'icici', 'hdfc', 'mufg', 'nuvama', 'ksh', 'offer', 'directors',
        'promoters', 'shareholder', 'pursuant', 'excludes', 'reference',
        'managerial', 'personnel', 'secondary', 'transfer', 'selling',
        'pre', 'post', 'key', 'executive', 'non', 'whole', 'time',
    }
    
    def __init__(self, nlp_model):
        self.nlp = nlp_model
    
    def detect(self, text: str) -> List[PIIEntity]:
        out = []
        doc = self.nlp(text)
        
        for ent in doc.ents:
            if ent.label_ != "PERSON":
                continue
            
            name_lower = ent.text.lower()
            words = name_lower.split()
            
            # Multi-layer filtering
            if name_lower in self.PLACE_NAMES:
                continue
            if any(w in self.PLACE_NAMES for w in words):
                continue
            if any(w in self.INSTITUTIONAL for w in words):
                continue
            if len(words) == 1 and len(words[0]) < 4:
                continue
            if 'family trust' in name_lower:
                continue
            if len(words) > 2 and 'and' in words[1:-1]:
                continue
            
            out.append(PIIEntity(ent.start_char, ent.end_char, ent.text, "PERSON", 0.85))
        
        # Heuristic: Title + 2-4 capitalized words
        title_pat = re.compile(r'\b(?:Mr|Mrs|Ms|Dr|Prof|Shri|Smt)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b')
        for m in title_pat.finditer(text):
            # Check overlap with existing
            if any(m.start() < e.end and m.end() > e.start for e in out):
                continue
            name_part = m.group(1).lower()
            words = name_part.split()
            if not any(w in self.PLACE_NAMES or w in self.INSTITUTIONAL for w in words):
                out.append(PIIEntity(m.start(), m.end(), m.group(), "PERSON", 0.75))
        
        return out


class AddressDetector(PIIDetector):
    """
    Detects physical addresses. By default preserves statutory labels
    (Registered Office, Corporate Office) but redacts the address value.
    """
    
    ADDR_KEYWORDS = re.compile(
        r'\b(?:Village|Plot\s+No|Tower|Floor|Road|Street|Lane|Block|Sector|'
        r'District|Taluka|Taluk|Tehsil|Maharashtra|Karnataka|Gujarat|'
        r'Delhi|Mumbai|Pune|Bangalore|Chennai|Kolkata|Hyderabad|'
        r'Pincode|PIN|Ahilyanagar|Ahmednagar|'
        r'Baner|Khed|Chakan|Raigad|Panvel|Padghe|Khalumbre|'
        r'Bandra|Kurla|Vikhroli|BKC|G\s*Block)\b',
        re.I
    )
    
    PIN_PATTERN = re.compile(r'\b\d{6}\b')
    
    STATUTORY = re.compile(
        r'^(Registered Office|Corporate Office|Head Office|Principal Office|'
        r'Office of|Address of)\s*[:\\-]?\s*',
        re.I
    )
    
    def __init__(self, preserve_statutory: bool = True):
        self.preserve_statutory = preserve_statutory
    
    def detect(self, text: str) -> List[PIIEntity]:
        out = []
        pos = 0
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                pos += len(line) + 1
                continue
            
            has_addr = self.ADDR_KEYWORDS.search(stripped) or self.PIN_PATTERN.search(stripped)
            if not has_addr:
                pos += len(line) + 1
                continue
            
            statutory_match = self.STATUTORY.match(stripped)
            
            if statutory_match and self.preserve_statutory:
                addr_start = statutory_match.end()
                addr_text = stripped[addr_start:].strip()
                if addr_text and len(addr_text) > 10:
                    start = pos + line.index(stripped) + addr_start
                    out.append(PIIEntity(start, start + len(addr_text), addr_text, "ADDRESS"))
            elif not statutory_match:
                start = pos + line.index(stripped)
                out.append(PIIEntity(start, start + len(stripped), stripped, "ADDRESS"))
            
            pos += len(line) + 1
        
        return out


class CompanyDetector(PIIDetector):
    """
    Detects company names. Redaction is OFF by default per policy
    (preserve institutional/statutory info).
    """
    
    STATUTORY = {'sebi', 'bse', 'nse', 'nsdl', 'cdsl', 'rbi', 'roc', 'goi',
                 'securities and exchange board', 'stock exchange',
                 'reserve bank', 'income tax'}
    
    def __init__(self, nlp_model, redact_enabled: bool = False):
        self.nlp = nlp_model
        self.redact_enabled = redact_enabled
    
    def detect(self, text: str) -> List[PIIEntity]:
        if not self.redact_enabled:
            return []
        
        out = []
        doc = self.nlp(text)
        
        for ent in doc.ents:
            if ent.label_ == "ORG":
                if any(s in ent.text.lower() for s in self.STATUTORY):
                    continue
                out.append(PIIEntity(ent.start_char, ent.end_char, ent.text, "COMPANY", 0.80))
        
        comp_pat = re.compile(
            r'\b[A-Z][a-zA-Z&\s]+(?:Limited|Ltd\.?|Private\s+Limited|LLP|LLC|Inc\.?|Corporation|Corp\.?|PLC)\b',
            re.I
        )
        for m in comp_pat.finditer(text):
            if any(m.start() < e.end and m.end() > e.start for e in out):
                continue
            if not any(s in m.group().lower() for s in self.STATUTORY):
                out.append(PIIEntity(m.start(), m.end(), m.group(), "COMPANY", 0.70))
        
        return out

class RedactionEngine:
    """
    Orchestrates detection, conflict resolution, and replacement.
    """
    
    LABEL_PRIORITY = {
        "EMAIL": 10, "PHONE": 10, "IP_ADDRESS": 10, "SSN": 10,
        "CREDIT_CARD": 10, "PAN": 10, "CIN": 10,
        "DOB": 9, "ADDRESS": 8, "PERSON": 7, "COMPANY": 6,
    }
    
    def __init__(self, nlp_model, dfaker: DeterministicFaker, 
                 redact_companies: bool = False, 
                 preserve_statutory_addresses: bool = True):
        self.dfaker = dfaker
        self.detectors = [
            EmailDetector(),
            PhoneDetector(),
            IPDetector(),
            SSNDetector(),
            CreditCardDetector(),
            DOBDetector(),
            PANDetector(),
            CINDetector(),
            AddressDetector(preserve_statutory=preserve_statutory_addresses),
            NameDetector(nlp_model),
            CompanyDetector(nlp_model, redact_enabled=redact_companies),
        ]
    
    def detect_all(self, text: str) -> List[PIIEntity]:
        all_ents = []
        for det in self.detectors:
            try:
                all_ents.extend(det.detect(text))
            except Exception as e:
                print(f"[WARN] {det.__class__.__name__}: {e}")
        
        all_ents.sort(key=lambda e: (e.start, -(e.end - e.start)))
        
        resolved = []
        for ent in all_ents:
            overlap = False
            for existing in resolved:
                if ent.start < existing.end and ent.end > existing.start:
                    ent_pri = self.LABEL_PRIORITY.get(ent.label, 0)
                    ex_pri = self.LABEL_PRIORITY.get(existing.label, 0)
                    ent_len = ent.end - ent.start
                    ex_len = existing.end - existing.start
                    
                    if ent_pri > ex_pri or (ent_pri == ex_pri and ent_len > ex_len):
                        resolved.remove(existing)
                        break  # will add ent below
                    else:
                        overlap = True
                        break
            if not overlap:
                resolved.append(ent)
        
        resolved.sort(key=lambda e: e.start)
        return resolved
    
    def redact_text(self, text: str) -> Tuple[str, List[Tuple[str, str, str]]]:
        ents = self.detect_all(text)
        replacements = [(e.start, e.end, e.text, self.dfaker.get(e.text, e.label), e.label) 
                        for e in ents]
        
        
        redacted = text
        log = []
        for start, end, orig, fake, label in sorted(replacements, key=lambda x: x[0], reverse=True):
            redacted = redacted[:start] + fake + redacted[end:]
            log.append((orig, fake, label))
        
        log.reverse()
        return redacted, log

