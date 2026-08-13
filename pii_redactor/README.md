# PII Redactor

Redacts Personally Identifiable Information (PII) from DOCX documents and replaces sensitive entities with consistent fake data.

## Features

- **Hybrid Detection:** Uses regular expressions with validation logic (Luhn checksums, IPv4 ranges, SSN pattern constraints) alongside spaCy NER for named entities.
- **Deterministic Pseudonyms:** Maps identical PII entities to the same synthetic replacement using MD5 hashing over pre-generated pools.
- **Context-Aware Rules:** Distinguishes between personal and corporate emails, preserves statutory office address labels, and filters out institutional entity false positives.
- **DOCX Structure Preservation:** Updates document XML runs to replace text while preserving inline styles and document layouts.

## Supported PII Types

- Full Names (`PERSON`)
- Email Addresses (`EMAIL`)
- Phone Numbers (`PHONE`)
- Company Names (`COMPANY`, configurable)
- Physical Addresses (`ADDRESS`)
- Social Security Numbers (`SSN`)
- Credit Card Numbers (`CREDIT_CARD`)
- Dates of Birth (`DOB`)
- IP Addresses (`IP_ADDRESS`)
- PAN & CIN Numbers (`PAN`, `CIN`)

## Quick Start

### Installation

```bash
cd pii_redactor
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Usage

Basic redaction:

```bash
python cli.py "../docs/Red Herring Prospectus.docx" "../output/redacted.docx"
```

Options:

```bash
# Print mapping log
python cli.py "../docs/Red Herring Prospectus.docx" "../output/redacted.docx" --verbose

# Redact company names as well
python cli.py "../docs/Red Herring Prospectus.docx" "../output/redacted.docx" --redact-companies
```

### Running Tests

```bash
python -m pytest tests/test_detectors.py -v
```

### Evaluation

To score against the gold standard sample:

```bash
python evaluate.py
```

## Module Overview

- `cli.py`: CLI entry point.
- `evaluate.py`: Evaluation runner and report generator.
- `redactor/detectors.py`: Pattern matching and validation detectors.
- `redactor/classify.py`: Rules for filtering corporate vs. personal identifiers.
- `redactor/ner.py`: Named entity recognition heuristics.
- `redactor/addresses.py`: Address parser and statutory label preserver.
- `redactor/docx_io.py`: DOCX document reader and XML run modifier.
- `redactor/pipeline.py`: Detection orchestration and conflict resolution.
- `redactor/pseudonyms.py`: Deterministic fake value generator.
