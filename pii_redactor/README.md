# PII Redactor

Automated tool to detect and redact Personally Identifiable Information (PII) from DOCX documents and replace sensitive entities with consistent pseudonyms.

## Features

- **Hybrid Detection:** Combines regular expressions with strict validation (Luhn algorithm, IPv4 octets, SSN pattern rules) and spaCy NER for names.
- **Deterministic Pseudonyms:** Maps matching PII entities to stable fake replacements using MD5 hashing.
- **Contextual Rules:** Differentiates personal vs corporate emails, preserves statutory office address labels, and filters out false positive institutional entities.
- **DOCX Run Preservation:** Modifies XML text runs directly to preserve document styling and layout.

## Supported PII Types

- Full Names (`PERSON`)
- Email Addresses (`EMAIL`)
- Phone Numbers (`PHONE`)
- Company Names (`COMPANY`, opt-in)
- Physical Addresses (`ADDRESS`)
- Social Security Numbers (`SSN`)
- Credit Card Numbers (`CREDIT_CARD`)
- Dates of Birth (`DOB`)
- IP Addresses (`IP_ADDRESS`)
- PAN & CIN Numbers (`PAN`, `CIN`)

## Execution Options

### Option 1: Docker (Recommended)

Run without local Python setup issues:

```bash
# Using Docker Compose
docker compose up --build

# Or using plain Docker
docker build -t pii-redactor .
docker run --rm -v "${PWD}/docs:/app/docs" -v "${PWD}/output:/app/output" pii-redactor
```

### Option 2: Local Python Environment

```bash
# 1. Install dependencies
cd pii_redactor
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Run redaction
python cli.py "../docs/Red Herring Prospectus.docx" "../output/redacted.docx"

# 3. Run evaluation
python evaluate.py

# 4. Run unit tests
python -m pytest tests/test_detectors.py -v
```

## Directory Structure

```
.
├── Dockerfile
├── docker-compose.yml
├── run.py
├── docs/
│   └── Red Herring Prospectus.docx
├── output/
│   └── redacted.docx
├── evaluation/
│   ├── gold_standard.json
│   └── evaluation_report.md
└── pii_redactor/
    ├── cli.py
    ├── evaluate.py
    ├── requirements.txt
    ├── redactor/
    │   ├── detectors.py
    │   ├── classify.py
    │   ├── ner.py
    │   ├── addresses.py
    │   ├── docx_io.py
    │   ├── pipeline.py
    │   └── pseudonyms.py
    └── tests/
        └── test_detectors.py
```
