import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from redactor.pipeline import PIIPipeline, RedactionConfig
from redactor.pseudonyms import DeterministicFaker
from redactor.docx_io import process_docx


def compute_metrics(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def run_evaluation(gold_path: str, config: RedactionConfig, seed: int) -> None:
    pipeline = PIIPipeline(config)
    dfaker = DeterministicFaker(seed)

    with open(gold_path, encoding="utf-8") as f:
        gold_data = json.load(f)

    label_tp = Counter()
    label_fp = Counter()
    label_fn = Counter()

    for item in gold_data:
        text = item["text"]
        gold_spans = {
            (a["start"], a["end"], a["label"]) for a in item["annotations"]
        }
        pred_spans = pipeline.detect_all(text)
        pred_set = {(s.start, s.end, s.label) for s in pred_spans}

        for g in gold_spans:
            if g in pred_set:
                label_tp[g[2]] += 1
            else:
                label_fn[g[2]] += 1

        for p in pred_set:
            if p not in gold_spans:
                label_fp[p[2]] += 1

    all_labels = sorted(set(list(label_tp.keys()) + list(label_fn.keys()) + list(label_fp.keys())))
    print("\n=== EVALUATION REPORT ===\n")
    print(f"{'Label':<16} {'TP':>5} {'FP':>5} {'FN':>5}  {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print("-" * 72)

    total_tp = total_fp = total_fn = 0
    for lbl in all_labels:
        tp, fp, fn = label_tp[lbl], label_fp[lbl], label_fn[lbl]
        total_tp += tp
        total_fp += fp
        total_fn += fn
        m = compute_metrics(tp, fp, fn)
        print(
            f"{lbl:<16} {tp:>5} {fp:>5} {fn:>5}  "
            f"{m['precision']:>10.3f} {m['recall']:>8.3f} {m['f1']:>8.3f}"
        )

    print("-" * 72)
    overall = compute_metrics(total_tp, total_fp, total_fn)
    print(
        f"{'OVERALL':<16} {total_tp:>5} {total_fp:>5} {total_fn:>5}  "
        f"{overall['precision']:>10.3f} {overall['recall']:>8.3f} {overall['f1']:>8.3f}"
    )
    print()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python cli.py",
        description="PII Redaction Tool for DOCX documents.",
    )
    p.add_argument("input", nargs="?", help="Input .docx file path")
    p.add_argument("output", nargs="?", help="Output (redacted) .docx path")
    p.add_argument(
        "--redact-companies", action="store_true",
        help="Also redact company / organisation names",
    )
    p.add_argument(
        "--redact-all-phones", action="store_true",
        help="Redact all phone numbers including toll-free / fax",
    )
    p.add_argument(
        "--redact-co-emails", action="store_true",
        help="Also redact corporate email addresses",
    )
    p.add_argument(
        "--no-preserve-addrs", action="store_true",
        help="Redact entire address blocks including statutory labels",
    )
    p.add_argument(
        "--spacy-model", default="en_core_web_sm",
        help="spaCy model name (default: en_core_web_sm)",
    )
    p.add_argument(
        "--seed", type=int, default=42,
        help="Seed for deterministic faker (default: 42)",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Print replacements",
    )
    p.add_argument(
        "--evaluate", metavar="GOLD_JSON",
        help="Run precision/recall evaluation against a gold-standard JSON file",
    )
    return p


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = RedactionConfig(
        redact_companies=args.redact_companies,
        preserve_statutory_addresses=not args.no_preserve_addrs,
        redact_company_emails=args.redact_co_emails,
        redact_all_phones=args.redact_all_phones,
        spacy_model=args.spacy_model,
    )

    if args.evaluate:
        run_evaluation(args.evaluate, config, args.seed)
        return

    if not args.input or not args.output:
        parser.error("Both <input> and <output> are required for redaction mode.")

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading spaCy model '{config.spacy_model}'...")
    pipeline = PIIPipeline(config)
    dfaker = DeterministicFaker(seed=args.seed)

    print(f"Processing: {input_path}")
    log = process_docx(str(input_path), str(output_path), pipeline, dfaker)

    print(f"\nSaved redacted document to: {output_path}")
    print(f"Total replacements: {len(log)}")

    label_counts = Counter(lbl for _, _, lbl in log)
    print("\nReplacements by type:")
    for lbl in sorted(label_counts):
        print(f"  {lbl:<16}: {label_counts[lbl]}")

    if args.verbose and log:
        print("\nMapping table:")
        print(f"  {'Original':<45} {'Replacement':<45} {'Label'}")
        print("  " + "-" * 110)
        for orig, fake, lbl in log:
            print(f"  {orig[:44]:<45} {fake[:44]:<45} {lbl}")


if __name__ == "__main__":
    main()
