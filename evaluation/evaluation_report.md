# PII Redaction Evaluation Report

**Date:** 2026-08-14  
**Dataset:** Stratified Sample (`evaluation/gold_standard.json`)  
**Method:** Hybrid Rule-Based & NER Model  

---

## Entity Metrics Summary

| Entity Label | TP | FP | FN | Precision | Recall | F1 Score |
|---|---|---|---|---|---|---|
| ADDRESS | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| CIN | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| CREDIT_CARD | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| DOB | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| EMAIL | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| IP_ADDRESS | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| PAN | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| PERSON | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| PHONE | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| SSN | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| **OVERALL** | **16** | **0** | **0** | **1.000** | **1.000** | **1.000** |

---

## Evaluation Approach

1. **Stratified Gold Standard:** Evaluated against a representative sample of 20 annotated snippets containing personal identifiers, financial data, company IDs, addresses, and negative controls.
2. **Precision & Recall Calculation:** Measured exact token span matches and entity label accuracy.
3. **False Positive Prevention:** Tested against statutory body names (SEBI, RBI, BSE), corporate domains, and non-sensitive ticket/reference numbers to verify precision.

---

## Trade-offs & Limitations

- **Company Redaction:** Disabled by default to preserve institutional and statutory disclosures within legal prospectuses. Can be enabled via `--redact-companies`.
- **Date Matching:** Dates require contextual birth keywords (e.g. "date of birth", "born on") to avoid false positives on financial year dates.
- **Names in Prose:** Unprefixed human names relies primarily on spaCy `en_core_web_sm` model predictions, filtered against known place names and institutional terms.
