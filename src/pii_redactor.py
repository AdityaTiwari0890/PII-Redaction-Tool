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