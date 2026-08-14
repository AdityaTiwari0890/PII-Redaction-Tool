import sys
import re
from dataclasses import dataclass
from typing import List, Tuple
import spacy

from redactor.detectors import PIISpan, all_structured_detectors
from redactor.ner import NameDetector, CompanyDetector
from redactor.addresses import AddressDetector
from redactor.classify import is_personal_email, is_personal_phone
from redactor.pseudonyms import DeterministicFaker


@dataclass
class RedactionConfig:
    redact_companies: bool = False
    preserve_statutory_addresses: bool = True
    redact_company_emails: bool = False
    redact_all_phones: bool = False
    spacy_model: str = "en_core_web_sm"


_PRIORITY = {
    "EMAIL": 10,
    "PHONE": 10,
    "IP_ADDRESS": 10,
    "SSN": 10,
    "CREDIT_CARD": 10,
    "PAN": 10,
    "CIN": 10,
    "DOB": 9,
    "ADDRESS": 8,
    "PERSON": 7,
    "COMPANY": 6,
}


def _resolve_overlaps(spans: List[PIISpan]) -> List[PIISpan]:
    spans.sort(
        key=lambda s: (s.start, -(s.end - s.start), -_PRIORITY.get(s.label, 0))
    )

    resolved = []
    for span in spans:
        conflict = False
        for i, kept in enumerate(resolved):
            if span.start < kept.end and span.end > kept.start:
                sp = _PRIORITY.get(span.label, 0)
                kp = _PRIORITY.get(kept.label, 0)
                sl = span.end - span.start
                kl = kept.end - kept.start
                if sp > kp or (sp == kp and sl > kl):
                    resolved[i] = span
                conflict = True
                break
        if not conflict:
            resolved.append(span)

    resolved.sort(key=lambda s: s.start)
    return resolved


class PIIPipeline:
    def __init__(self, config: RedactionConfig = None):
        self.config = config or RedactionConfig()
        try:
            self._nlp = spacy.load(self.config.spacy_model)
        except Exception:
            try:
                import subprocess
                subprocess.run([sys.executable, "-m", "spacy", "download", self.config.spacy_model], check=True)
                self._nlp = spacy.load(self.config.spacy_model)
            except Exception:
                self._nlp = spacy.blank("en")

        self._detectors = [
            *all_structured_detectors(),
            AddressDetector(
                preserve_statutory=self.config.preserve_statutory_addresses
            ),
            NameDetector(self._nlp),
            CompanyDetector(self._nlp, enabled=self.config.redact_companies),
        ]

    def detect_all(self, text: str) -> List[PIISpan]:
        raw = []
        for det in self._detectors:
            try:
                raw.extend(det.detect(text))
            except Exception as exc:
                print(f"[WARN] {det.__class__.__name__} failed: {exc}")

        filtered = []
        for span in raw:
            if span.label == "EMAIL":
                if is_personal_email(span.text):
                    filtered.append(span)
                elif self.config.redact_company_emails:
                    filtered.append(span)

            elif span.label == "PHONE":
                lo = max(0, span.start - 40)
                hi = min(len(text), span.end + 10)
                ctx = text[lo:hi]
                if self.config.redact_all_phones or is_personal_phone(span.text, ctx):
                    filtered.append(span)

            else:
                filtered.append(span)

        return _resolve_overlaps(filtered)

    def redact_text(
        self,
        text: str,
        dfaker: DeterministicFaker,
    ) -> Tuple[str, List[Tuple[str, str, str]]]:
        spans = self.detect_all(text)
        if not spans:
            return text, []

        replacements = [
            (s.start, s.end, s.text, dfaker.get(s.text, s.label), s.label)
            for s in spans
        ]

        redacted = text
        log = []
        for start, end, orig, fake, label in sorted(
            replacements, key=lambda x: x[0], reverse=True
        ):
            redacted = redacted[:start] + fake + redacted[end:]
            log.append((orig, fake, label))

        log.reverse()
        return redacted, log
