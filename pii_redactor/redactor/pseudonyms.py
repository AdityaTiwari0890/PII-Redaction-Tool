"""
pseudonyms.py
=============
Deterministic stable fake-value generator.

Design:
  - MD5 hash of (original_text + label) → stable index into a pre-seeded pool.
  - Same input always returns the same synthetic replacement (idempotent across runs).
  - Indian-locale pool (Faker 'en_IN') keeps replacements contextually plausible.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Tuple

from faker import Faker


class DeterministicFaker:
    """
    Generates stable, contextually plausible fake values.

    Usage:
        dfaker = DeterministicFaker(seed=42)
        fake_name = dfaker.get("Rashi Patil", "PERSON")
        # returns same value every time for "Rashi Patil"
    """

    # Pool sizes — large enough to avoid obvious collisions on a 300-page doc
    _POOL_SIZES: Dict[str, int] = {
        "PERSON":      500,
        "EMAIL":       500,
        "PHONE":       300,
        "COMPANY":     200,
        "ADDRESS":     200,
        "SSN":         100,
        "CREDIT_CARD": 100,
        "DOB":         100,
        "IP_ADDRESS":  100,
        "PAN":         100,
        "CIN":         100,
    }

    def __init__(self, seed: int = 42) -> None:
        self._cache: Dict[Tuple[str, str], str] = {}
        fake = Faker("en_IN")
        fake.seed_instance(seed)

        self._pools: Dict[str, list[str]] = {
            "PERSON": [fake.name() for _ in range(self._POOL_SIZES["PERSON"])],
            "EMAIL":  [fake.email() for _ in range(self._POOL_SIZES["EMAIL"])],
            "PHONE":  [
                f"+91 {fake.msisdn()[3:]}"
                for _ in range(self._POOL_SIZES["PHONE"])
            ],
            "COMPANY": [fake.company() for _ in range(self._POOL_SIZES["COMPANY"])],
            "ADDRESS": [
                fake.address().replace("\n", ", ")
                for _ in range(self._POOL_SIZES["ADDRESS"])
            ],
            "SSN": [fake.ssn() for _ in range(self._POOL_SIZES["SSN"])],
            "CREDIT_CARD": [
                fake.credit_card_number(card_type="visa")
                for _ in range(self._POOL_SIZES["CREDIT_CARD"])
            ],
            "DOB": [
                fake.date_of_birth(minimum_age=25, maximum_age=65).strftime(
                    "%B %d, %Y"
                )
                for _ in range(self._POOL_SIZES["DOB"])
            ],
            "IP_ADDRESS": [
                fake.ipv4() for _ in range(self._POOL_SIZES["IP_ADDRESS"])
            ],
            "PAN": [
                fake.bothify(
                    text="?????#####?", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                )
                for _ in range(self._POOL_SIZES["PAN"])
            ],
            "CIN": [
                fake.bothify(
                    text="U#####??####PLC######",
                    letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                )
                for _ in range(self._POOL_SIZES["CIN"])
            ],
        }

    # ------------------------------------------------------------------
    def get(self, original: str, label: str) -> str:
        """
        Return the stable fake replacement for *original* with *label*.
        The mapping is cached in memory so repeated lookups are O(1).
        """
        key = (original.strip(), label)
        if key not in self._cache:
            pool = self._pools.get(label)
            if pool:
                idx = (
                    int(hashlib.md5((original + label).encode()).hexdigest(), 16)
                    % len(pool)
                )
                self._cache[key] = pool[idx]
            else:
                self._cache[key] = "[REDACTED]"
        return self._cache[key]

    # ------------------------------------------------------------------
    def mapping_table(self) -> list[tuple[str, str, str]]:
        """Return all (original, fake, label) triples generated so far."""
        return [(orig, fake, lbl) for (orig, lbl), fake in self._cache.items()]
