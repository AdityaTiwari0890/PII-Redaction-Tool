"""
Simple runner script to execute redaction on the prospectus document.
"""

import sys
from pathlib import Path

# Add pii_redactor package directory to path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir / "pii_redactor"))

from redactor.pipeline import PIIPipeline, RedactionConfig
from redactor.pseudonyms import DeterministicFaker
from redactor.docx_io import process_docx

def main():
    input_file = root_dir / "docs" / "Red Herring Prospectus.docx"
    output_dir = root_dir / "output"
    output_file = output_dir / "redacted.docx"

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading input: {input_file}")
    config = RedactionConfig()
    pipeline = PIIPipeline(config)
    faker = DeterministicFaker(seed=42)

    log = process_docx(str(input_file), str(output_file), pipeline, faker)
    print(f"Redaction complete! Output saved to: {output_file}")
    print(f"Total entities redacted: {len(log)}")

if __name__ == "__main__":
    main()
