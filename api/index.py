from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path
import tempfile
import os

# Add root directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "pii_redactor"))

from redactor.pipeline import PIIPipeline, RedactionConfig
from redactor.pseudonyms import DeterministicFaker
from redactor.docx_io import process_docx

app = FastAPI(title="PII Redaction API", description="Serverless PII Redactor for DOCX files")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "PII Redactor API"}

@app.post("/api/redact")
async def redact_docx(
    file: UploadFile = File(...),
    redact_companies: bool = Form(False),
    seed: int = Form(42)
):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.docx")
        output_path = os.path.join(tmpdir, "redacted.docx")

        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

        config = RedactionConfig(redact_companies=redact_companies)
        pipeline = PIIPipeline(config)
        dfaker = DeterministicFaker(seed=seed)

        log = process_docx(input_path, output_path, pipeline, dfaker)

        with open(output_path, "rb") as f:
            redacted_bytes = f.read()

        filename_base = os.path.splitext(file.filename)[0]
        out_filename = f"{filename_base}_redacted.docx"

        # Return file response with metadata header
        headers = {
            "Content-Disposition": f'attachment; filename="{out_filename}"',
            "X-Redaction-Count": str(len(log))
        }

        return Response(
            content=redacted_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers
        )
