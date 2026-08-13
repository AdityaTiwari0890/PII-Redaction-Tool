import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from redactor.pipeline import PIIPipeline, RedactionConfig
from redactor.pseudonyms import DeterministicFaker


def compute_metrics(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4),
            "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


def evaluate(gold_path: str, config: RedactionConfig) -> tuple:
    pipeline = PIIPipeline(config)

    with open(gold_path, encoding="utf-8") as f:
        gold_data = json.load(f)

    label_tp = Counter()
    label_fp = Counter()
    label_fn = Counter()
    errors = []

    for item in gold_data:
        text = item["text"]
        gold_spans = {
            (a["start"], a["end"], a["label"])
            for a in item.get("annotations", [])
        }

        pred_spans_raw = pipeline.detect_all(text)
        pred_set = {(s.start, s.end, s.label) for s in pred_spans_raw}

        for g in gold_spans:
            if g in pred_set:
                label_tp[g[2]] += 1
            else:
                label_fn[g[2]] += 1
                errors.append({
                    "id": item.get("id", "?"),
                    "type": "FN",
                    "label": g[2],
                    "missed": text[g[0]:g[1]],
                    "text": text[:120],
                })

        for p in pred_set:
            if p not in gold_spans:
                label_fp[p[2]] += 1
                errors.append({
                    "id": item.get("id", "?"),
                    "type": "FP",
                    "label": p[2],
                    "spurious": text[p[0]:p[1]],
                    "text": text[:120],
                })

    all_labels = sorted(set(
        list(label_tp) + list(label_fp) + list(label_fn)
    ))
    results = {}
    for lbl in all_labels:
        results[lbl] = compute_metrics(label_tp[lbl], label_fp[lbl], label_fn[lbl])

    total_tp = sum(label_tp.values())
    total_fp = sum(label_fp.values())
    total_fn = sum(label_fn.values())
    results["OVERALL"] = compute_metrics(total_tp, total_fp, total_fn)

    return results, errors


def write_report(results: dict, errors: list, report_path: str, config: RedactionConfig) -> None:
    lines = [
        "# PII Redaction Tool - Evaluation Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Gold standard: evaluation/gold_standard.json",
        "Approach: Hybrid (regex + Luhn/SSN validation + spaCy NER + contextual rules)",
        f"Company redaction: {'enabled' if config.redact_companies else 'disabled (default)'}",
        "",
        "---",
        "",
        "## Entity-Level Metrics",
        "",
        "| Label | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---|---|---|---|---|---|",
    ]

    all_labels = [k for k in results if k != "OVERALL"]
    for lbl in sorted(all_labels):
        m = results[lbl]
        lines.append(
            f"| {lbl} | {m['tp']} | {m['fp']} | {m['fn']} "
            f"| {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} |"
        )

    m = results["OVERALL"]
    lines += [
        f"| **OVERALL** | **{m['tp']}** | **{m['fp']}** | **{m['fn']}** "
        f"| **{m['precision']:.3f}** | **{m['recall']:.3f}** | **{m['f1']:.3f}** |",
        "",
        "---",
        "",
        "## Methodology",
        "",
        "### Ground Truth",
        "A manually annotated stratified sample of 20 text snippets was used as the gold standard.",
        "Strata covered: personal emails, phone numbers, structured IDs (PAN, CIN, SSN, IP, Credit Card, DOB),",
        "addresses (personal vs statutory), director names (title-prefixed, ALL-CAPS, key-value), and",
        "explicit negative controls (place names, statutory orgs, ticket numbers).",
        "",
        "### Metrics Definition",
        "- TP = gold-standard span (start, end, label) exactly matched by prediction",
        "- FP = predicted span not in gold standard",
        "- FN = gold-standard span not predicted",
        "- Span matching is exact (boundary + label).",
        "",
        "### Evaluation Scope",
        "Entity-level precision/recall are computed on the stratified sample.",
        "",
        "---",
        "",
        "## Tradeoffs & Observations",
        "",
        "| Type | Decision | Rationale |",
        "|---|---|---|",
        "| Company names | Not redacted by default | Preserve institutional/statutory info |",
        "| Corporate emails | Not redacted by default | Only personal (gmail, yahoo, etc.) domains are flagged |",
        "| Toll-free phones | Not redacted | 1800-prefixed numbers are institutional contact lines |",
        "| Statutory addresses | Value redacted, label preserved | Regulatory requirement |",
        "| ALL-CAPS 2+ word tokens | Flagged as candidate names | Promoter-list tables in RHP use all-caps |",
        "| CIN numbers | Redacted | Contains company ID & filing identifier |",
        "",
        "### Known False Positives",
        "- ALL-CAPS sector/industry abbreviations (e.g., 'MIDC AREA') may occasionally be flagged",
        "  as PERSON if they form 2+ word sequences not in the stop-list.",
        "",
        "### Known False Negatives",
        "- Names mentioned only once in flowing prose without a title prefix or key-value label may be missed if spaCy NER misclassifies them.",
        "- DOB detection requires a contextual keyword within +-120 chars; standalone date strings are skipped.",
        "",
        "---",
        "",
        "## Extending the Tool",
        "",
        "To add a new PII type (e.g. Aadhaar number):",
        "1. Create a class in redactor/detectors.py inheriting RegexDetector.",
        "2. Add the label to _PRIORITY in redactor/pipeline.py.",
        "3. Add a pool generator for the label in redactor/pseudonyms.py.",
        "4. Register the detector in redactor/pipeline.py.",
        "5. Add unit tests in tests/test_detectors.py.",
        "",
    ]

    if errors:
        lines += [
            "## Error Analysis",
            "",
            "| ID | Type | Label | Span |",
            "|---|---|---|---|",
        ]
        for e in errors[:40]:
            span = e.get("missed") or e.get("spurious", "?")
            lines.append(f"| {e['id']} | {e['type']} | {e['label']} | `{span[:60]}` |")
        lines.append("")

    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"Report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate PII redaction pipeline.")
    parser.add_argument(
        "--gold",
        default="../evaluation/gold_standard.json",
        help="Path to gold-standard annotation JSON",
    )
    parser.add_argument(
        "--report",
        default="../evaluation/evaluation_report.md",
        help="Path to write the markdown evaluation report",
    )
    parser.add_argument(
        "--redact-companies", action="store_true",
        help="Enable company-name redaction",
    )
    args = parser.parse_args()

    config = RedactionConfig(redact_companies=args.redact_companies)

    print("Running evaluation...")
    results, errors = evaluate(args.gold, config)

    print(f"\n{'Label':<16} {'TP':>4} {'FP':>4} {'FN':>4}  {'Prec':>6} {'Recall':>7} {'F1':>6}")
    print("-" * 60)
    for lbl in sorted(k for k in results if k != "OVERALL"):
        m = results[lbl]
        print(f"{lbl:<16} {m['tp']:>4} {m['fp']:>4} {m['fn']:>4}  {m['precision']:>6.3f} {m['recall']:>7.3f} {m['f1']:>6.3f}")
    print("-" * 60)
    m = results["OVERALL"]
    print(f"{'OVERALL':<16} {m['tp']:>4} {m['fp']:>4} {m['fn']:>4}  {m['precision']:>6.3f} {m['recall']:>7.3f} {m['f1']:>6.3f}")
    print()

    write_report(results, errors, args.report, config)


if __name__ == "__main__":
    main()
